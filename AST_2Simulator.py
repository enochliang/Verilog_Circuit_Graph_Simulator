from AST_Schedule import *
from abc import ABC, abstractmethod


class Verilog_AST_Construction_Exception(Exception):
    def __init__(self, message, error_code):
        super().__init__(message)
        self.error_code = error_code

    def __str__(self):
        return f"{self.args[0]} (Error Code: {self.error_code})"

# Define the RTL Circuit Graph Node Data Structure
class Node:
    def __init__(self,name:str,width:int,value:str,node_type:str,fault_list:dict):
        self.name = name # "Signal_B"
        self.width = width # 5
        self.value = value # "xxxxx"
        self.node_type = node_type # "Wire", "FF_in", "FF_out", "OP"
        self.fault_list = fault_list # {"Signal_A":0.9 , ...}
        self.ready_flag = False
        self.attrib = dict()

    def set_fault_list(self,fault_list:dict):
        self.fault_list = fault_list
    def set_value(self,value:str):
        if "x" in value:
            raise SimulationError("Error: Set X Value",1)
        self.value = value
    def set_attrib(self,attrib:dict):
        for key in attrib.keys():
            self.attrib[key] = attrib[key]
    def get_info(self):
        pprint.pp(self.__dict__)


class Verilog_AST_Base_Node:
    def __init__(self):
        self.__tag = ""
        self.__children = []
        self.attrib = dict()

    @property
    def children(self):
        return self.__children

    @children.setter
    def children(self,value:list):
        self.__children = value

    def append(self,node):
        self.__children.append(node)

    @abstractmethod
    def tag(self):
        pass

class Verilog_AST_Node(Verilog_AST_Base_Node):
    def __init__(self):
        Verilog_AST_Base_Node.__init__(self)

    @property
    def tag(self):
        return self.__tag

    @tag.setter
    def tag(self,tag:str):
        self.__tag = tag

class Verilog_AST_Control_Node(Verilog_AST_Node):
    def __init__(self):
        Verilog_AST_Node.__init__(self)

    @property
    def ctrl_sig_id(self):
        if len(self.__children) < 1:
            return None
        else:
            return self.__children[0]

class Verilog_AST_IF_Node(Verilog_AST_Control_Node):
    def __init__(self):
        Verilog_AST_Control_Node.__init__(self)
        self.__tag = "if"
        self.__true_id = None
        self.__false_id = None

    @property
    def true_id(self):
        if len(self.__children) < 2:
            return None
        else:
            return self.__children[1]

    @property
    def false_id(self):
        if len(self.__children) < 3:
            return None
        else:
            return self.__children[2]

class Verilog_AST_CASE_Node(Verilog_AST_Control_Node):
    def __init__(self):
        Verilog_AST_Control_Node.__init__(self)
        self.__tag = "case"
        self.__caseitem_ids = []

    @property
    def caseitem_ids(self):
        return self.__caseitem_ids

    def append(self,idx:int):
        self.__caseitem_ids.append(idx)

class Verilog_AST_CASEITEM_Node(Verilog_AST_Node):
    def __init__(self):
        Verilog_AST_Node.__init__(self)
        self.__tag = "caseitem"
        self.__condition_ids = []

    @property
    def condition_ids(self):
        return self.__condition_ids

    def add_condition(self,idx):
        self.__condition_ids.append(idx)

    @property
    def other_children(self):
        return self.__children[len(self.__condition_ids):]


class Verilog_AST_Circuit_Node(Verilog_AST_Node):
    def __init__(self,width:int):
        Verilog_AST_Node.__init__(self)
        self.__width = width
        self.__value = "x"*self.__width

    @property
    def width(self):
        return self.__width

    @property
    def value(self):
        return self.__value

    @value.setter
    def value(self,value:str):
        if len(value) == self.__width:
            self.__value = value
        else:
            raise Verilog_AST_Construction_Exception("value and width doesn't match.",0)

class Verilog_AST_Var_Node(Verilog_AST_Circuit_Node):
    def __init__(self,width:int):
        Verilog_AST_Circuit_Node.__init__(self,width)
        self.__tag = "var"

    @property
    def name(self):
        return self.__name

    @name.setter
    def name(self,value:str):
        self.__name = value

class Verilog_AST_Varref_Node(Verilog_AST_Circuit_Node):
    def __init__(self,width:int):
        Verilog_AST_Circuit_Node.__init__(self,width)
        self.__tag = "varref"

    @property
    def name(self):
        return self.__name

    @name.setter
    def name(self,value:str):
        self.__name = value

class AST_2Simulator:
    def __init__(self,ast):
        ast_scheduler = AST_Schedule(ast)
        ast_scheduler.proc()
        self._ast = ast_scheduler._ast

        self.subcircuit_num = ast_scheduler.subcircuit_num
        ast_scheduler.ordered_subcircuit_id_head
        ast_scheduler.ordered_subcircuit_id_tail

    def ast_construct(self):
        self.ast_node_list = []
        self.__map__subcircuit_id_2_ast_id = {}
        self.__map__var_name_2_ast_id = {}

        self.count_xml_ast_node()
        self.append_var_node()
        self.append_ast_node()
        self.count_my_ast_node()
        #print(self.__map__var_name_2_ast_id)
        #print(self.__map__subcircuit_id_2_ast_id)

    def append_var_node(self):
        print("start adding <var> nodes into ast... ")
        for var in self._ast.findall(".//module//var"):
            width = int(var.attrib["width"])
            name = var.attrib["name"]

            new_node_id = len(self.ast_node_list)
            new_var_node = Verilog_AST_Var_Node(width)
            new_var_node.name = name

            self.ast_node_list.append(new_var_node)
            self.__map__var_name_2_ast_id[name] = new_node_id

    def add_ast_child(self,node):
        children = node.getchildren()
        children_id = []
        for child in children:
            children_id.append(self.add_ast_child(child))
        new_node_id = len(self.ast_node_list)

        if node.tag == "varref":
            name = node.attrib["name"]
            width = int(node.attrib["width"])
            new_node = Verilog_AST_Varref_Node(width)
            new_node.name = name
        elif "dtype_id" in node.attrib:
            width = int(node.attrib["width"])
            new_node = Verilog_AST_Circuit_Node(width)
            new_node.tag = node.tag
        else:
            if node.tag == "case":
                new_node = Verilog_AST_CASE_Node()
            elif node.tag == "if":
                new_node = Verilog_AST_IF_Node()
            elif node.tag == "caseitem":
                new_node = Verilog_AST_CASEITEM_Node()
            else:
                new_node = Verilog_AST_Node()
                new_node.tag = node.tag

        new_node.children = children_id
        self.ast_node_list.append(new_node)

        return new_node_id

    def append_ast_node(self):
        for subcircuit_id in range(self.subcircuit_num):
            entry_node = self._ast.find(f".//*[@subcircuit_id='{str(subcircuit_id)}']")
            entry_node_id = self.add_ast_child(entry_node)
            self.__map__subcircuit_id_2_ast_id[subcircuit_id] = entry_node_id

    def count_xml_ast_node(self):
        self.count_xml_var_node()
        self.count_xml_subcircuit_node()

    def count_xml_var_node(self):
        var_num = 0
        for var in self._ast.findall(".//module//var"):
            var_num += 1
        print(f"Total Number of <var> = {var_num}")

    def count_xml_subcircuit_node(self):
        ast_node_num = 0
        for subcircuit_id in range(self.subcircuit_num):
            subcircuit = self._ast.find(f".//*[@subcircuit_id='{str(subcircuit_id)}']")
            for node in subcircuit.iter():
                ast_node_num += 1
        print(f"Total Number of AST Nodes = {ast_node_num}")

    def count_my_ast_node(self):
        self.count_my_var_node()
        self.count_my_subcircuit_node()

    def count_my_var_node(self):
        print(f"Total Number of <var> in my ast = {len(self.__map__var_name_2_ast_id)}")

    def count_my_subcircuit_node(self):
        ast_node_num = 0
        for key, idx in self.__map__subcircuit_id_2_ast_id.items():
            ast_node_num += len(self.iter_my_node(self.ast_node_list[idx]))
        print(f"Total Number of subcircuit nodes in my ast = {ast_node_num}")

    def iter_my_node(self,node):
        node_list = []
        node_list.append(node)
        for child_id in node.children:
            child_node = self.ast_node_list[child_id]
            node_list = node_list + self.iter_my_node(child_node)
        return node_list


    def execute(self,node)


if __name__ == "__main__":
    # Step 1: Create the parser
    parser = argparse.ArgumentParser(description="A simple example of argparse usage.")

    # Step 2: Define arguments
    parser.add_argument("ast", type=str, help="AST path")                  # Positional argument

    # Step 3: Parse the arguments
    args = parser.parse_args()

    ast_file = args.ast
    ast = Verilator_AST_Tree(ast_file)

    #for always in ast.findall(".//always"):
    #    for node in AST_Analyzer.dfs_iter(always):
    #        print(node.tag)
    #    print("-"*80)
    ast_sim = AST_2Simulator(ast)
    ast_sim.ast_construct()

