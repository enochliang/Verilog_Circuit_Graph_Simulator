from lxml import etree
import pprint 
import argparse
import json

class RTL_Coding_Style_Warning(Exception):
    def __init__(self, message, error_code):
        super().__init__(message)
        self.error_code = error_code

    def __str__(self):
        return f"{self.args[0]} (Error Code: {self.error_code})"
class Unconsidered_Case(Exception):
    def __init__(self, message, error_code):
        super().__init__(message)
        self.error_code = error_code

    def __str__(self):
        return f"{self.args[0]} (Error Code: {self.error_code})"


class AST_Analyzer:
    def __init__(self, ast: etree._ElementTree):
       self.ast = ast

    # Convert a Verilog Format Number to a Decimal Python Number
    def verilog_num2num(self,num:str):
        width = None
        sign = None
        if "'" in num:
            split_num = num.split("'")
            width = split_num[0]
            if "s" in split_num[1]:
                radix = split_num[1][0:2]
                new_num = split_num[1][2:]
                sign = "1"
            else:
                radix = split_num[1][0]
                new_num = split_num[1][1:]
                sign = "0"
            if (radix == "h" or radix == "sh"):
                new_num = str(int(new_num,16))
            elif (radix == "d"):
                new_num = str(int(new_num,10))
            elif (radix == "o"):
                new_num = str(int(new_num,8))
            elif(radix == "b"):
                new_num = str(int(new_num,2))
            else:
                print("Error: Unknown Radix!")
                print(f"    Num = {num}")
        else:
            print("Warning: Not A Verilog Formatted Number.")
            print(f"    Num = {num}")
            new_num = num
        return {"width":width,"val":new_num,"sign":sign}

    def get_info(self):
        pprint.pp(self.__dir__())

    def get_all_signal(self,output=True):
        # Make a List of All Signals Including WIRE & Flip-Flop.
        signals = set()
        for var in self.ast.findall(".//assignalias//*[2]") + self.ast.findall(".//contassign//*[2]") + self.ast.findall(".//always//assign//*[2]") + self.ast.findall(".//always//assigndly//*[2]"):
            if var.tag != "varref":
                print("Error: LV is not a varref.")
                print("    Tag: "+var.tag)
            else:
                signals.add(var.attrib["name"])
        if output:
            print("Print All Signals Including WIRE & Flip-Flop...")
            for sig in signals:
                print("  "+sig)
        return signals

    def _show_all_submodname(self):
        submodname_dict = {}
        for module in self.ast.findall(".//module"):
            orig_name = module.attrib["origName"]
            inst_name = module.attrib["name"]
            params = {}
            for param in module.findall(".//var[@param='true']"):
                params[param.attrib["name"]] = param.find("./const").attrib["name"]
            inst_info = (inst_name, params)
            if orig_name in submodname_dict:
                submodname_dict[orig_name].append(inst_info)
            else:
                submodname_dict[orig_name] = [inst_info]
        pprint.pp(submodname_dict)

    def get_dtype_width(self,dtype):
        if dtype.tag == "basicdtype":
            if "left" in dtype.attrib:
                left = int(dtype.attrib['left'])
                right = int(dtype.attrib['right'])
                return abs(right - left) + 1
            else:
                return 1
        elif dtype.tag == "memberdtype" or dtype.tag == "refdtype" or dtype.tag == "enumdtype":
            sub_dtype_id = dtype.attrib["sub_dtype_id"]
            return self.get_dtype_width(self.ast.find(f".//typetable/*[@id='{sub_dtype_id}']"))
        elif dtype.tag == "structdtype":
            width = 0
            for memberdtype in dtype.getchildren():
                width += self.get_dtype_width(memberdtype)
            return width
        elif dtype.tag == "unpackarraydtype" or dtype.tag == "packarraydtype":
            sub_dtype_id = dtype.attrib["sub_dtype_id"]
            left_num = int(self.verilog_num2num(dtype.find(".//range/const[1]").attrib["name"])["val"])
            right_num = int(self.verilog_num2num(dtype.find(".//range/const[2]").attrib["name"])["val"])
            return self.get_dtype_width(self.ast.find(f".//typetable/*[@id='{sub_dtype_id}']")) * (abs(left_num - right_num) + 1)
        elif dtype.tag == "voiddtype":
            return 0
        else:
            print("Error!!")


    def get_dtype_shape(self,dtype):
        if dtype.tag == "voiddtype":
            return ""
        elif dtype.tag == "basicdtype":
            if "left" in dtype.attrib:
                return f"[{dtype.attrib['left']}:{dtype.attrib['right']}] X "
            else:
                return "[0] X "
        elif dtype.tag == "unpackarraydtype":
            sub_dtype_id = dtype.attrib["sub_dtype_id"]
            left_num = self.verilog_num2num(dtype.find(".//range/const[1]").attrib["name"])["val"]
            right_num = self.verilog_num2num(dtype.find(".//range/const[2]").attrib["name"])["val"]
            return self.get_dtype_shape(self.ast.find(f".//typetable/*[@id='{sub_dtype_id}']")) + f"[{left_num}:{right_num}]" 
        elif dtype.tag == "packarraydtype":
            sub_dtype_id = dtype.attrib["sub_dtype_id"]
            left_num = self.verilog_num2num(dtype.find(".//range/const[1]").attrib["name"])["val"]
            right_num = self.verilog_num2num(dtype.find(".//range/const[2]").attrib["name"])["val"]
            return f"[{left_num}:{right_num}]" + self.get_dtype_shape(self.ast.find(f".//typetable/*[@id='{sub_dtype_id}']"))
        elif dtype.tag == "refdtype" or dtype.tag == "enumdtype":
            sub_dtype_id = dtype.attrib["sub_dtype_id"]
            return self.get_dtype_shape(self.ast.find(f".//typetable/*[@id='{sub_dtype_id}']"))
        elif dtype.tag == "structdtype":
            width = self.get_dtype_width(dtype)
            return f"[{width-1}:0]X"
        else:
            print(f"Error-{dtype.tag}")


    def get_dict__dtypeid_2_width(self,output=True) -> dict:
        dtypeid_2_width_dict = {}
        for dtype in self.ast.find(".//typetable").getchildren():
            dtypeid_2_width_dict[dtype.attrib["id"]] = self.get_dtype_width(dtype)
            if dtypeid_2_width_dict[dtype.attrib["id"]] == 0:
                print(f"    warning: dtype_id = {dtype.attrib['id']}, width = {dtypeid_2_width_dict[dtype.attrib['id']]}")
        return dtypeid_2_width_dict

    def get_dict__dtypeid_2_shape(self,output=True) -> dict:
        dtypeid_2_shape_dict = {}
        for dtype in self.ast.find(".//typetable").getchildren():
            dtypeid_2_shape_dict[dtype.attrib["id"]] = self.get_dtype_shape(dtype)
        return dtypeid_2_shape_dict

    def get_dict__signame_2_width(self,sig_list):
        dtypeid_2_width_dict = self.get_dict__dtypeid_2_width()
        signame_2_width_dict = {}
        for sig_name in sig_list:
            var_node = self.ast.find(f".//var[@name='{sig_name}']")
            width = dtypeid_2_width_dict[var_node.attrib["dtype_id"]]
            signame_2_width_dict[sig_name] = width
        return signame_2_width_dict

    def get_dtypetable_as_dict(self,output=True) -> dict:
        dtypes_dict = dict()
        for node in self.ast.find(".//typetable").getchildren():
            if node.tag == "voiddtype":
                continue
            if "name" in node.attrib:
                if node.attrib["id"] in dtypes_dict.keys():
                    raise Exception("Repeated dtype_id!")
                dtypes_dict[node.attrib["id"]] = node.attrib["name"]
            basic_node = self._search_basic_dtype(node)
            dtypes_dict[node.attrib["id"]] = basic_node.attrib["name"]
        if output:
            print("Dtypetable Dictionary:")
            for dtype in dtypes_dict.items():
                print("  "+str(dtype))
        return dtypes_dict
    def _search_basic_dtype(self,node):
        if node.tag == "structdtype":
            return self._search_basic_dtype(node.getchildren()[0])
        else:
            if "sub_dtype_id" in node.attrib:
                ref_id = node.attrib["sub_dtype_id"]
                next_node = self.ast.find(".//typetable/*[@id='"+ref_id+"']")
                return self._search_basic_dtype(next_node)
            else:
                return node

    def get_n_logic_dtype(self,output=True) -> set:
        # Get the List Dtypes That is Not a Logic or Bit.
        n_logic_dtypes = set()
        for dtype in self.ast.findall(".//typetable//basicdtype"):
            if dtype.attrib["name"] == "logic":
                pass
            elif dtype.attrib["name"] == "bit":
                pass
            else:
                n_logic_dtypes.add(dtype.attrib["name"])
        #for dtype in self.ast.findall(".//typetable//basicdtype"):
        if output:
            for dtype in n_logic_dtypes:
                print(dtype)


    def get_sig_nodes(self,output=True) -> set:
        var_set = set()
        dtype_dict = self.get_dtypetable_as_dict(output=False)
        for var in self.ast.findall(".//module//var"):
            if "param" in var.attrib:
                pass
            elif "localparam" in var.attrib:
                pass
            else:
                dtype = dtype_dict[var.attrib["dtype_id"]]
                if dtype == "int" or dtype == "integer":
                    pass
                else:
                    var_set.add(var.attrib['name'])
        if output:
            for var in var_set:
                print(var)
        return var_set

    def get_all_tags_under(self,target="verilator_xml",output=True) -> set:
        # Make a List of All Kinds of Tags.
        tags = set()
        target_nodes = self.ast.findall(".//"+target)
        if target_nodes:
            for t_node in target_nodes:
                for node in t_node.iter():
                    tags.add(node.tag)
            if output:
                print("get all tags under <"+target+">:")
                for tag in tags:
                    print("  <"+tag+">")
        return tags

    def get_unique_children_under(self,target="verilator_xml",output=True) -> list:
        # Make a List of All Kinds of Tags.
        children = []
        children = self.get_ordered_children_under(target,False)
        children_set = set()
        for ls in children:
            for c in ls:
                children_set.add(c)
        if output:
            pprint.pp(children_set)
        return children_set

    def get_ordered_children(self,node):
        return [child_node.tag for child_node in node.getchildren()]

    def get_ordered_children_under(self,target="verilator_xml",output=True) -> list:
        # Make a List of All Kinds of Tags.
        childrens = []
        target_nodes = self.ast.findall(".//"+target)
        if target_nodes:
            for t_node in target_nodes:
                children = get_ordered_children(t_node)
                if not children in childrens:
                    childrens.append(children)
            if output:
                print("get ordered children under <"+target+">:")
                for c in childrens:
                    print("  "+str(c))
        return childrens


    def get_signal_dicts(self):
        # Check AST Simple
        #self.check_simple_design()

        print("Getting Signal Lists...")
        # Get Signal List
        input_var_list = self.get_input_port()
        ff_var_list = self.get_ff()
        output_var_list = self.get_output_port()
       
        #faultfree_input_list = input_var_list + ff_var_list
        #injection_list = ff_var_list
        #observation_list = ff_var_list + output_var_list

        input_var_dict = {}
        for var in input_var_list:
            dtype_id = self.ast.find(f".//var[@name='{var}']").attrib["dtype_id"]
            dtype = self.ast.find(f".//basicdtype[@id='{dtype_id}']")
            if "left" in dtype.attrib:
                left = int(dtype.attrib["left"])
                right = int(dtype.attrib["right"])
            else:
                left = 0
                right = 0
            input_var_dict[var] = left - right + 1
        ff_var_dict = {}
        for var in ff_var_list:
            dtype_id = self.ast.find(f".//var[@name='{var}']").attrib["dtype_id"]
            dtype = self.ast.find(f".//basicdtype[@id='{dtype_id}']")
            if "left" in dtype.attrib:
                left = int(dtype.attrib["left"])
                right = int(dtype.attrib["right"])
            else:
                left = 0
                right = 0
            ff_var_dict[var] = left - right + 1
        output_var_dict = {}
        for var in output_var_list:
            dtype_id = self.ast.find(f".//var[@name='{var}']").attrib["dtype_id"]
            dtype = self.ast.find(f".//basicdtype[@id='{dtype_id}']")
            if "left" in dtype.attrib:
                left = int(dtype.attrib["left"])
                right = int(dtype.attrib["right"])
            else:
                left = 0
                right = 0
            output_var_dict[var] = left - right + 1
        print("DONE!!!")
        return {"input":input_var_dict,"ff":ff_var_dict,"output":output_var_dict}

    def _get_lv_sig_name(self,node):
        if node.tag == "varref":
            sig_name = node.attrib["name"]
            return sig_name
        elif node.tag == "sel" or node.tag == "arraysel":
            return self._get_lv_sig_name(node.getchildren()[0])
        else:
            raise Unconsidered_Case("",0)
    def _get_lv_sig_node(self,node):
        if node.tag == "varref":
            return node
        elif node.tag == "sel" or node.tag == "arraysel":
            return self._get_lv_sig_node(node.getchildren()[0])
        else:
            raise Unconsidered_Case("",0)

    def get_lv(self):
        return [self._get_lv_sig_name(assign.getchildren()[1]) for assign in self.ast.findall(".//initial//assign") + self.ast.findall(".//always//assigndly") + self.ast.findall(".//always//assign") + self.ast.findall(".//contassign")]

    def get_input_port(self):
        return [var.attrib["name"] for var in self.ast.findall(".//var[@dir='input']")]

    def get_ff(self):
        return [self._get_lv_sig_name(assigndly.getchildren()[1]) for assigndly in self.ast.findall(".//assigndly")]

    def get_output_port(self):
        ff_list = self.get_ff()
        return [var.attrib["name"] for var in self.ast.findall(".//var[@dir='output']") if not var.attrib["name"] in ff_list]

    def dump_sig_dict(self, file_name, sig_dict):
        with open(file_name,"w") as f:
            f.write(json.dumps(sig_dict, indent=4))
            f.close()




def Verilator_AST_Tree(ast_file_path:str) -> etree._ElementTree:
    return etree.parse(ast_file_path)


if __name__ == "__main__":
    # Step 1: Create the parser
    parser = argparse.ArgumentParser(description="A simple example of argparse usage.")

    # Step 2: Define arguments
    parser.add_argument("ast", type=str, help="AST path")                  # Positional argument

    # Step 3: Parse the arguments
    args = parser.parse_args()

    ast_file = args.ast
    ast = Verilator_AST_Tree(ast_file)
    print("#"*len("# Start analyzing ["+ast_file+"] #"))
    print("# Start parsing ["+ast_file+"] #")
    print("#"*len("# Start analyzing ["+ast_file+"] #"))
    analyzer = AST_Analyzer(ast)
    analyzer.get_ordered_children_under("arraysel")


