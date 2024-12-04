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

class AST_Analysis_Function:
    def __init__(self, ast: etree._ElementTree):
       self.ast = ast

    def help(self):
        pprint.pp(self.__dir__())

    @staticmethod
    # Convert a Verilog Format Number to a Decimal Python Number
    def verilog_num2num(num:str):
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

    @staticmethod
    def vnum2bin(num:str):
        sign = None
        if "'" in num:
            split_num = num.split("'")
            width = int(split_num[0])
            if "s" in split_num[1]:
                radix = split_num[1][0:2]
                new_num = split_num[1][2:]
                sign = "1"
            else:
                radix = split_num[1][0]
                new_num = split_num[1][1:]
                sign = "0"
            if "x" in new_num:
                return "x"*width
            elif "z" in new_num:
                return "z"*width
            else:
                if (radix == "h" or radix == "sh"):
                    new_num = int(new_num,16)
                elif (radix == "d"):
                    new_num = int(new_num,10)
                elif (radix == "o"):
                    new_num = int(new_num,8)
                elif(radix == "b"):
                    new_num = int(new_num,2)
                else:
                    print("Error: Unknown Radix!")
                    print(f"    Num = {num}")
        else:
            print("Warning: Not A Verilog Formatted Number.")
            print(f"    Num = {num}")
            new_num = num

        new_num = bin(new_num)[2:]
        d = width - len(new_num)
        new_num = "0"*d + new_num
        return new_num


    @staticmethod
    def dfs_iter(node):
        children = node.getchildren()
        node_list = []
        if len(children) > 0:
            for child in children:
                node_list += AST_Analysis_Function.dfs_iter(child)
        node_list.append(node)
        return node_list
    @staticmethod
    def dfs_iter_until_assign(node):
        children = node.getchildren()
        node_list = []
        if len(children) > 0 and not "assign" in node.tag:
            if node.tag == "if" or node.tag == "case":
                for child in children[1:]:
                    node_list += AST_Analysis_Function.dfs_iter_until_assign(child)
            elif node.tag == "caseitem":
                for child in children:
                    if "dtype_id" in child.attrib:
                        continue
                    node_list += AST_Analysis_Function.dfs_iter_until_assign(child)
            else:
                for child in children:
                    node_list += AST_Analysis_Function.dfs_iter_until_assign(child)
        node_list.append(node)
        return node_list

    @staticmethod
    def get_dtype__not_logic(ast,output=True) -> set:
        # Get the List Dtypes That is Not a Logic or Bit.
        n_logic_dtypes = set()
        for dtype in ast.findall(".//typetable//basicdtype"):
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
        return n_logic_dtypes

    @staticmethod
    def get_dtype_width(dtype):
        ast = dtype.getroottree().getroot()
        if dtype.tag == "basicdtype":
            if "left" in dtype.attrib:
                left = int(dtype.attrib['left'])
                right = int(dtype.attrib['right'])
                return abs(right - left) + 1
            else:
                return 1
        elif dtype.tag == "memberdtype" or dtype.tag == "refdtype" or dtype.tag == "enumdtype":
            sub_dtype_id = dtype.attrib["sub_dtype_id"]
            return AST_Analysis_Function.get_dtype_width(ast.find(f".//typetable/*[@id='{sub_dtype_id}']"))
        elif dtype.tag == "structdtype":
            width = 0
            for memberdtype in dtype.getchildren():
                width += AST_Analysis_Function.get_dtype_width(memberdtype)
            return width
        elif dtype.tag == "unpackarraydtype" or dtype.tag == "packarraydtype":
            sub_dtype_id = dtype.attrib["sub_dtype_id"]
            left_num = int(AST_Analysis_Function.verilog_num2num(dtype.find(".//range/const[1]").attrib["name"])["val"])
            right_num = int(AST_Analysis_Function.verilog_num2num(dtype.find(".//range/const[2]").attrib["name"])["val"])
            return AST_Analysis_Function.get_dtype_width(ast.find(f".//typetable/*[@id='{sub_dtype_id}']")) * (abs(left_num - right_num) + 1)
        elif dtype.tag == "voiddtype":
            return 0
        else:
            print("Error!!")

    @staticmethod
    def get_dtype_shape(dtype):
        ast = dtype.getroottree().getroot()
        if dtype.tag == "voiddtype":
            return ""
        elif dtype.tag == "basicdtype":
            if "left" in dtype.attrib:
                return f"[{dtype.attrib['left']}:{dtype.attrib['right']}] X "
            else:
                return "[0] X "
        elif dtype.tag == "unpackarraydtype":
            sub_dtype_id = dtype.attrib["sub_dtype_id"]
            left_num = AST_Analysis_Function.verilog_num2num(dtype.find(".//range/const[1]").attrib["name"])["val"]
            right_num = AST_Analysis_Function.verilog_num2num(dtype.find(".//range/const[2]").attrib["name"])["val"]
            return AST_Analysis_Function.get_dtype_shape(ast.find(f".//typetable/*[@id='{sub_dtype_id}']")) + f"[{left_num}:{right_num}]" 
        elif dtype.tag == "packarraydtype":
            sub_dtype_id = dtype.attrib["sub_dtype_id"]
            left_num = AST_Analysis_Function.verilog_num2num(dtype.find(".//range/const[1]").attrib["name"])["val"]
            right_num = AST_Analysis_Function.verilog_num2num(dtype.find(".//range/const[2]").attrib["name"])["val"]
            return f"[{left_num}:{right_num}]" + AST_Analysis_Function.get_dtype_shape(ast.find(f".//typetable/*[@id='{sub_dtype_id}']"))
        elif dtype.tag == "refdtype" or dtype.tag == "enumdtype":
            sub_dtype_id = dtype.attrib["sub_dtype_id"]
            return AST_Analysis_Function.get_dtype_shape(ast.find(f".//typetable/*[@id='{sub_dtype_id}']"))
        elif dtype.tag == "structdtype":
            width = AST_Analysis_Function.get_dtype_width(dtype)
            return f"[{width-1}:0]X"
        else:
            print(f"Error-{dtype.tag}")

    @staticmethod
    def show_all_submodname(ast):
        submodname_dict = {}
        for module in ast.findall(".//module"):
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

    @staticmethod
    def get_dict__dtypeid_2_width(ast):
        dtypeid_2_width_dict = {}
        for dtype in ast.find(".//typetable").getchildren():
            dtypeid_2_width_dict[dtype.attrib["id"]] = AST_Analysis_Function.get_dtype_width(dtype)
            if dtypeid_2_width_dict[dtype.attrib["id"]] == 0:
                print(f"    warning: dtype_id = {dtype.attrib['id']}, width = {dtypeid_2_width_dict[dtype.attrib['id']]}")
        return dtypeid_2_width_dict

    @staticmethod
    def get_dict__dtypeid_2_shape(ast) -> dict:
        dtypeid_2_shape_dict = {}
        for dtype in ast.find(".//typetable").getchildren():
            dtypeid_2_shape_dict[dtype.attrib["id"]] = AST_Analysis_Function.get_dtype_shape(dtype)
        return dtypeid_2_shape_dict
    
    @staticmethod
    def get_dict__signame_2_width(ast,sig_list):
        dtypeid_2_width_dict = AST_Analysis_Function.get_dict__dtypeid_2_width(ast)
        signame_2_width_dict = {}
        for sig_name in sig_list:
            var_node = ast.find(f".//var[@name='{sig_name}']")
            width = dtypeid_2_width_dict[var_node.attrib["dtype_id"]]
            signame_2_width_dict[sig_name] = width
        return signame_2_width_dict

    @staticmethod
    def get_dict__dtypetable(ast,output=True) -> dict:
        dtypes_dict = dict()
        for node in ast.find(".//typetable").getchildren():
            if node.tag == "voiddtype":
                continue
            if "name" in node.attrib:
                if node.attrib["id"] in dtypes_dict.keys():
                    raise Exception("Repeated dtype_id!")
                dtypes_dict[node.attrib["id"]] = node.attrib["name"]
            basic_node = AST_Analysis_Function.search_basic_dtype(node)
            dtypes_dict[node.attrib["id"]] = basic_node.attrib["name"]
        if output:
            print("Dtypetable Dictionary:")
            for dtype in dtypes_dict.items():
                print("  "+str(dtype))
        return dtypes_dict

    @staticmethod
    def get_dict__signal_table(ast):
        # Check AST Simple
        #self.check_simple_design()

        print("Getting Signal Lists...")
        # Get Signal List
        input_var_list =  AST_Analysis_Function.get_sig__input_port(ast)
        ff_var_list =     AST_Analysis_Function.get_sig__ff(ast)
        output_var_list = AST_Analysis_Function.get_sig__output_port(ast)
       
        #faultfree_input_list = input_var_list + ff_var_list
        #injection_list = ff_var_list
        #observation_list = ff_var_list + output_var_list

        input_var_dict = {}
        for var in input_var_list:
            dtype_id = ast.find(f".//var[@name='{var}']").attrib["dtype_id"]
            dtype = ast.find(f".//basicdtype[@id='{dtype_id}']")
            if "left" in dtype.attrib:
                left = int(dtype.attrib["left"])
                right = int(dtype.attrib["right"])
            else:
                left = 0
                right = 0
            input_var_dict[var] = left - right + 1
        ff_var_dict = {}
        for var in ff_var_list:
            dtype_id = ast.find(f".//var[@name='{var}']").attrib["dtype_id"]
            dtype = ast.find(f".//basicdtype[@id='{dtype_id}']")
            if "left" in dtype.attrib:
                left = int(dtype.attrib["left"])
                right = int(dtype.attrib["right"])
            else:
                left = 0
                right = 0
            ff_var_dict[var] = left - right + 1
        output_var_dict = {}
        for var in output_var_list:
            dtype_id = ast.find(f".//var[@name='{var}']").attrib["dtype_id"]
            dtype = ast.find(f".//basicdtype[@id='{dtype_id}']")
            if "left" in dtype.attrib:
                left = int(dtype.attrib["left"])
                right = int(dtype.attrib["right"])
            else:
                left = 0
                right = 0
            output_var_dict[var] = left - right + 1
        print("DONE!!!")
        return {"input":input_var_dict,"ff":ff_var_dict,"output":output_var_dict}

    @staticmethod
    def get_children__ordered(node):
        return [child_node.tag for child_node in node.getchildren()]

    @staticmethod
    def get_children__ordered_under(ast,target="verilator_xml",output=True) -> list:
        # Make a List of All Kinds of Tags.
        childrens = []
        target_nodes = ast.findall(".//"+target)
        if target_nodes:
            for t_node in target_nodes:
                children = AST_Analysis_Function.get_children__ordered(t_node)
                if not children in childrens:
                    childrens.append(children)
            if output:
                print("get ordered children under <"+target+">:")
                for c in childrens:
                    print("  "+str(c))
        return childrens

    @staticmethod
    def get_tag__all_under(ast,target="verilator_xml",output=True) -> set:
        # Make a List of All Kinds of Tags.
        tags = set()
        target_nodes = ast.findall(".//"+target)
        if target_nodes:
            for t_node in target_nodes:
                for node in t_node.iter():
                    tags.add(node.tag)
            if output:
                print("get all tags under <"+target+">:")
                for tag in tags:
                    print("  <"+tag+">")
        return tags

    @staticmethod
    def search_basic_dtype(node):
        if node.tag == "structdtype":
            return self._search_basic_dtype(node.getchildren()[0])
        else:
            if "sub_dtype_id" in node.attrib:
                ref_id = node.attrib["sub_dtype_id"]
                next_node = self.ast.find(".//typetable/*[@id='"+ref_id+"']")
                return self._search_basic_dtype(next_node)
            else:
                return node

    @staticmethod
    def node_has_child(node):
        return len(node.getchildren()) > 0
    @staticmethod
    def get_sig_name(node):
        target_node = AST_Analysis_Function.get_sig_node(node)
        return target_node.attrib["name"]
    @staticmethod
    def get_sig_node(node):
        if node.tag == "varref":
            return node
        elif node.tag == "sel" or node.tag == "arraysel":
            return AST_Analysis_Function.get_sig_node(node.getchildren()[0])
        else:
            raise Unconsidered_Case("",0)

    @staticmethod
    def get_sig__all(ast,output=True) -> set:
        var_set = set()
        dtype_dict = AST_Analysis_Function.get_dict__dtypetable(ast,output=False)
        for var in ast.findall(".//module//var"):
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

    @staticmethod
    def get_children_unique__under(ast,target="verilator_xml",output=True) -> list:
        # Make a List of All Kinds of Tags.
        children = []
        children = AST_Analysis_Function.get_children__ordered_under(ast,target,False)
        children_set = set()
        for ls in children:
            for c in ls:
                children_set.add(c)
        if output:
            pprint.pp(children_set)
        return children_set

    @staticmethod
    def get_sig__lv(ast):
        return [AST_Analysis_Function.get_sig_name(assign.getchildren()[1]) for assign in ast.findall(".//initial//assign") + ast.findall(".//always//assigndly") + ast.findall(".//always//assign") + ast.findall(".//contassign")]
    @staticmethod
    def get_sig__input_port(ast):
        return [var.attrib["name"] for var in ast.findall(".//var[@dir='input']")]
    @staticmethod
    def get_sig__ff(ast):
        return [AST_Analysis_Function.get_sig_name(assigndly.getchildren()[1]) for assigndly in ast.findall(".//assigndly")]
    @staticmethod
    def get_sig__output_port(ast):
        ff_list = AST_Analysis_Function.get_sig__ff(ast)
        return [var.attrib["name"] for var in ast.findall(".//var[@dir='output']") if not var.attrib["name"] in ff_list]

class AST_Analyzer:
    def __init__(self, ast: etree._ElementTree):
        self.ast = ast

    def show_all_submodname(self):
        return AST_Analysis_Function.show_all_submodname(self.ast)

    def get_dtype_width(self,dtype):
        return AST_Analysis_Function.get_dtype_width(dtype)

    def get_dtype_shape(self,dtype):
        return AST_Analysis_Function.get_dtype_shape(dtype)

    def get_dtype__not_logic(self,output=True) -> set:
        return AST_Analysis_Function.get_dtype__not_logic(self.ast,output)

    def get_dict__dtypeid_2_width(self) -> dict:
        return AST_Analysis_Function.get_dict__dtypeid_2_width(self.ast)

    def get_dict__dtypeid_2_shape(self) -> dict:
        return AST_Analysis_Function.get_dict__dtypeid_2_shape(self.ast)

    def get_dict__signame_2_width(self,sig_list):
        return AST_Analysis_Function.get_dict__signame_2_width(self.ast,sig_list)
 
    def get_dict__dtypetable(self,output=True) -> dict:
        return AST_Analysis_Function.get_dict__signame_2_width(self.ast,output)

    def get_dict__signal_table(self):
        return AST_Analysis_Function.get_dict__signal_table(self.ast)

    def search_basic_dtype(self,node):
        return AST_Analysis_Function.search_basic_dtype(self.ast)

    def get_tag__all_under(self,target="verilator_xml",output=True) -> set:
        return AST_Analysis_Function.get_tag__all_under(self.ast,target,output)

    def get_children_unique__under(self,target="verilator_xml",output=True) -> list:
        return AST_Analysis_Function.get_children_unique__under(self.ast,target,output)

    def get_children__ordered(self,node):
        return AST_Analysis_Function.get_children__ordered(node)

    def get_children__ordered_under(self,target="verilator_xml",output=True) -> list:
        return AST_Analysis_Function.get_children__ordered_under(self.ast,target,output)
    
    def get_sig__all(self,output=True) -> set:
        return AST_Analysis_Function.get_sig__all(self.ast,output)

    def get_sig__lv(self):
        return AST_Analysis_Function.get_sig__lv(self.ast)

    def get_sig__input_port(self):
        return AST_Analysis_Function.get_sig__input_port(self.ast)

    def get_sig__ff(self):
        return AST_Analysis_Function.get_sig__ff(self.ast)
    
    def get_sig__output_port(self):
        return AST_Analysis_Function.get_sig__output_port(self.ast)

    def dump_signal_table(self, file_name, signal_table):
        with open(file_name,"w") as f:
            f.write(json.dumps(signal_table, indent=4))
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
    pprint.pp(analyzer.get_dict__dtypeid_2_shape())


