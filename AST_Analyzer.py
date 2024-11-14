from lxml import etree
import pprint 

class RTL_Coding_Style_Warning(Exception):
    def __init__(self, message, error_code):
        super().__init__(message)
        self.error_code = error_code

    def __str__(self):
        return f"{self.args[0]} (Error Code: {self.error_code})"


class AST_Analyzer:
    def __init__(self, ast: etree._ElementTree):
       self.ast = ast

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
    def get_ordered_children_under(self,target="verilator_xml",output=True) -> list:
        # Make a List of All Kinds of Tags.
        childrens = []
        target_nodes = self.ast.findall(".//"+target)
        if target_nodes:
            for t_node in target_nodes:
                children = [node.tag for node in t_node.getchildren()]
                if not children in childrens:
                    childrens.append(children)
            if output:
                print("get ordered children under <"+target+">:")
                for c in childrens:
                    print("  "+str(c))
        return childrens


    def get_signal_dicts(self):
        # Check AST Simple
        self.check_simple_design()

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

    def get_input_port(self):
        return [var.attrib["name"] for var in self.ast.findall(".//var[@dir='input']")]

    def get_ff(self):
        return [assigndly.getchildren()[1].attrib["name"] for assigndly in self.ast.findall(".//assigndly")]

    def get_output_port(self):
        ff_list = self.get_ff()
        return [var.attrib["name"] for var in self.ast.findall(".//var[@dir='output']") if not var.attrib["name"] in ff_list]

def Verilator_AST_Tree(ast_file_path:str) -> etree._ElementTree:
    return etree.parse(ast_file_path)


if __name__ == "__main__":
    ast_file = "./ast/Vpicorv32_axi.xml"
    ast = Verilator_AST_Tree(ast_file)
    print("#"*len("# Start analyzing ["+ast_file+"] #"))
    print("# Start parsing ["+ast_file+"] #")
    print("#"*len("# Start analyzing ["+ast_file+"] #"))
    analyzer = AST_Analyzer(ast)
    #analyzer.get_info()
    #analyzer.check_simple_design()
    analyzer.get_ordered_children_under("caseitem")
    for a in ast.findall(".//caseitem/and"):
        print(a.attrib)


