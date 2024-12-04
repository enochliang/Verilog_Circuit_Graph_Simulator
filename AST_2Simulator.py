from AST_Schedule import *
from abc import ABC, abstractmethod


class Verilog_AST_Construction_Exception(Exception):
    def __init__(self, message, error_code):
        super().__init__(message)
        self.error_code = error_code

    def __str__(self):
        return f"{self.args[0]} (Error Code: {self.error_code})"


class Verilog_AST_Base_Node:
    def __init__(self):
        self._tag = ""
        self._children = []
        self.attrib = dict()

    @property
    def children(self):
        return self._children

    @children.setter
    def children(self,value:list):
        self._children = value

    def append(self,node):
        self._children.append(node)

    @abstractmethod
    def tag(self):
        pass

class Verilog_AST_Node(Verilog_AST_Base_Node):
    def __init__(self):
        Verilog_AST_Base_Node.__init__(self)

    @property
    def tag(self):
        return self._tag

    @tag.setter
    def tag(self,tag:str):
        self._tag = tag

class Verilog_AST_Control_Node(Verilog_AST_Node):
    def __init__(self):
        Verilog_AST_Node.__init__(self)

    @property
    def ctrl_sig_id(self):
        if len(self._children) < 1:
            return None
        else:
            return self._children[0]

class Verilog_AST_IF_Node(Verilog_AST_Control_Node):
    def __init__(self):
        Verilog_AST_Control_Node.__init__(self)
        self._tag = "if"
        self.__true_id = None
        self.__false_id = None

    @property
    def true_id(self):
        if len(self._children) < 2:
            return None
        else:
            return self._children[1]

    @property
    def false_id(self):
        if len(self._children) < 3:
            return None
        else:
            return self._children[2]

class Verilog_AST_CASE_Node(Verilog_AST_Control_Node):
    def __init__(self):
        Verilog_AST_Control_Node.__init__(self)
        self._tag = "case"
        self.__caseitem_ids = []

    @property
    def caseitem_ids(self):
        return self.__caseitem_ids

    def append(self,idx:int):
        self.__caseitem_ids.append(idx)

class Verilog_AST_CASEITEM_Node(Verilog_AST_Node):
    def __init__(self):
        Verilog_AST_Node.__init__(self)
        self._tag = "caseitem"
        self.__condition_ids = []

    @property
    def condition_ids(self):
        return self.__condition_ids

    def add_condition(self,idx):
        self.__condition_ids.append(idx)

    @property
    def other_children(self):
        return self._children[len(self.__condition_ids):]


class Verilog_AST_Circuit_Node(Verilog_AST_Node):
    def __init__(self,width:int):
        Verilog_AST_Node.__init__(self)
        self._width = width
        self._value = "x"*self._width

    @property
    def width(self):
        return self._width

    @property
    def value(self):
        return self._value

    @value.setter
    def value(self,value:str):
        if len(value) == self._width:
            self._value = value
        else:
            raise Verilog_AST_Construction_Exception("value and width doesn't match.",0)

class Verilog_AST_Var_Node(Verilog_AST_Circuit_Node):
    def __init__(self,width:int):
        Verilog_AST_Circuit_Node.__init__(self,width)
        self._tag = "var"

    @property
    def name(self):
        return self.__name

    @name.setter
    def name(self,value:str):
        self.__name = value

class Verilog_AST_Varref_Node(Verilog_AST_Circuit_Node):
    def __init__(self,width:int):
        Verilog_AST_Circuit_Node.__init__(self,width)
        self._tag = "varref"

    @property
    def name(self):
        return self.__name

    @name.setter
    def name(self,value:str):
        self.__name = value

    @property
    def ref_id(self):
        return self.__ref_id

    @ref_id.setter
    def ref_id(self,value:int):
        self.__ref_id = value



class AST_2Simulator:
    def __init__(self,ast):
        ast_scheduler = AST_Schedule(ast)
        ast_scheduler.proc()
        self._ast = ast_scheduler._ast

        self.subcircuit_num = ast_scheduler.subcircuit_num
        self.ordered_subcircuit_id_head = ast_scheduler.ordered_subcircuit_id_head
        self.ordered_subcircuit_id_tail = ast_scheduler.ordered_subcircuit_id_tail

    def convert(self):
        self.ast_construct()
        self.dump_var_name_dict()

    def ast_construct(self):
        self.ast_node_list = []
        self._map__subcircuit_id_2_ast_id = {}
        self._map__var_name_2_ast_id = {}
        self._dict__varname_2_width = {}

        self.append_var_node()
        self.append_ast_node()
        self.count_xml_ast_node()
        self.count_my_ast_node()

    def append_var_node(self):
        print("start adding <var> nodes into ast... ")
        for var in self._ast.findall(".//module//var"):
            width = int(var.attrib["width"])
            name = var.attrib["name"]

            new_node_id = len(self.ast_node_list)
            new_var_node = Verilog_AST_Var_Node(width)
            new_var_node.name = name

            self.ast_node_list.append(new_var_node)
            self._map__var_name_2_ast_id[name] = new_node_id
            self._dict__varname_2_width[name] = width


    def dump_var_name_dict(self):
        print("Dumped Varname Dict.")
        f = open("graph_sig_dict.json","w")
        f.write(json.dumps(self._dict__varname_2_width, indent=4))
        f.close()

    def _add_ast_varref(self,node):
        name = node.attrib["name"]
        width = int(node.attrib["width"])
        ref_id = self._map__var_name_2_ast_id[name]
        new_node = Verilog_AST_Varref_Node(width)
        new_node.name = name
        new_node.ref_id = ref_id
        return new_node

    def _add_ast_circuit_node(self,node):
        width = int(node.attrib["width"])
        new_node = Verilog_AST_Circuit_Node(width)
        new_node.tag = node.tag
        if node.tag == "const":
            value = node.attrib["name"]
            value = AST_Analysis_Function.vnum2bin(value)
            new_node.value = value
        return new_node

    def _add_ast_case(self):
        return Verilog_AST_CASE_Node()

    def _add_ast_if(self):
        return Verilog_AST_IF_Node()

    def _add_ast_caseitem(self,node,children_id):
        new_node = Verilog_AST_CASEITEM_Node()
        for idx, child in enumerate(node.getchildren()):
            if "dtype_id" in child.attrib:
                new_node.add_condition(children_id[idx])
        return new_node

    def add_ast_child(self,node):
        children = node.getchildren()
        children_id = []
        for child in children:
            children_id.append(self.add_ast_child(child))
        new_node_id = len(self.ast_node_list)

        if node.tag == "varref":
            new_node = self._add_ast_varref(node)
        elif "dtype_id" in node.attrib:
            new_node = self._add_ast_circuit_node(node)
        else:
            if node.tag == "case":
                new_node = self._add_ast_case()
            elif node.tag == "if":
                new_node = self._add_ast_if()
            elif node.tag == "caseitem":
                new_node = self._add_ast_caseitem(node,children_id)
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
            self._map__subcircuit_id_2_ast_id[subcircuit_id] = entry_node_id

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
        print(f"Total Number of <var> in my ast = {len(self._map__var_name_2_ast_id)}")

    def count_my_subcircuit_node(self):
        ast_node_num = 0
        for key, idx in self._map__subcircuit_id_2_ast_id.items():
            ast_node_num += len(self.iter_my_node(self.ast_node_list[idx]))
        print(f"Total Number of subcircuit nodes in my ast = {ast_node_num}")

    def iter_my_node(self,node):
        node_list = []
        node_list.append(node)
        for child_id in node.children:
            child_node = self.ast_node_list[child_id]
            node_list = node_list + self.iter_my_node(child_node)
        return node_list

class Simulator_Load_Logic(AST_2Simulator,AST_NodeClassify):
    def __init__(self,ast):
        AST_2Simulator.__init__(self,ast)
        AST_NodeClassify.__init__(self)

    def load_logic_value(self):
        pass


class Simulator_Execute(Simulator_Load_Logic):
    def __init__(self,ast):
        Simulator_Load_Logic.__init__(self,ast)


    def get_node(self,node_id):
        return self.ast_node_list[node_id]

    def execute_assign(self,node):
        right_node = self.get_node(node.children[0])
        width = right_node.width
        value = self.compute(right_node)

    def execute_if(self,node):
        ctrl_node = self.get_node(node.ctrl_sig_id)
        value = self.compute(ctrl_node)
        if "1" in value:
            true_node = self.get_node(node.true_id)
            self.execute(true_node)
        else:
            if node.false_id == None:
                pass
            else:
                false_node = self.get_node(node.false_id)
                self.execute(false_node)

    def execute_case(self,node):
        ctrl_node = self.get_node(node.ctrl_sig_id)
        value = self.compute(ctrl_node)
        for child_id in node.children[1:]:
            child_node = self.get_node(child_id)
            if self.execute_caseitem(child_node,value):
                break

    def execute_block(self,node):
        for child_id in node.children:
            child_node = self.get_node(child_id)
            self.execute(child_node)

    def execute(self,node):
        if "assign" in node.tag:
            self.execute_assign(node)
        else:
            if node.tag == "if":
                self.execute_if(node)
            elif node.tag == "case":
                self.execute_case(node)
            elif node.tag == "begin" or node.tag == "always":
                self.execute_block(node)
            else:
                print(f"Exception!!! tag = {node.tag}")

    def trigger_condition(self,node,ctrl_value:str):
        flag = False
        for condition_id in node.condition_ids:
            condition_node = self.get_node(condition_id)
            if self.compute(condition_node) == ctrl_value:
                flag = True
                break
        return (flag or (node.condition_ids == []))

    def execute_caseitem(self,node,ctrl_value:str):
        flag = self.trigger_condition(node,ctrl_value)
        if flag:
            for child_id in node.other_children:
                child_node = self.get_node(child_id)
                self.execute(child_node)
        return flag

    def compute(self,node):
        pass


class Simulator_Compute(Simulator_Execute):
    def __init__(self,ast):
        Simulator_Execute.__init__(self,ast)

    def compute(self,node):
        width = node.width
        if node.tag in self.op__2_port:
            right_node = self.get_node(node.children[0])
            left_node = self.get_node(node.children[1])
            r_value = self.compute(right_node)
            l_value = self.compute(left_node)
            if "x" in r_value+l_value:
                result = "x"*width
            elif "z" in r_value+l_value:
                result = "z"*width
            elif node.tag == "and":
                result = self.ast_and(r_value,l_value,width)
            elif node.tag == "or":
                result = self.ast_or(r_value,l_value,width)
            elif node.tag == "xor":
                result = self.ast_xor(r_value,l_value,width)
            elif node.tag == "add":
                result = self.ast_add(r_value,l_value,width)
            elif node.tag == "sub":
                result = self.ast_sub(r_value,l_value,width)
            elif node.tag == "muls":
                result = self.ast_muls(r_value,l_value,width)
            elif node.tag == "shiftl":
                result = self.ast_shiftl(r_value,l_value,width)
            elif node.tag == "shiftr":
                result = self.ast_shiftr(r_value,l_value,width)
            elif node.tag == "shiftrs":
                result = self.ast_shiftrs(r_value,l_value,width)
            elif node.tag == "eq":
                result = self.ast_eq(r_value,l_value)
            elif node.tag == "neq":
                result = self.ast_neq(r_value,l_value)
            elif node.tag == "gt":
                result = self.ast_gt(r_value,l_value)
            elif node.tag == "gte":
                result = self.ast_gte(r_value,l_value)
            elif node.tag == "lte":
                result = self.ast_lte(r_value,l_value)
            elif node.tag == "lt":
                result = self.ast_lt(r_value,l_value)
            elif node.tag == "concat":
                result = self.ast_concat(r_value,l_value)
            else:
                result = ""
        elif node.tag in self.op__1_port:
            input_node = self.get_node(node.children[0])
            i_value = self.compute(input_node)
            if "x" in i_value:
                result = "x"*width
            elif "z" in i_value:
                result = "z"*width
            elif node.tag == "not":
                result = self.ast_not(i_value)
        else:
            if node.tag == "arraysel":
                result = self.ast_arraysel(r_value,l_value,width)
            elif node.tag == "sel":
                result = self.ast_sel()
            result = ""
        
        return result

    # computation part
    def ast_and(self,rv,lv,width:int):
        result = int(rv, 2) & int(lv, 2)
        result = f"{result:0{width}b}"
        return result

    def ast_or(self,rv,lv,width:int):
        result = int(rv, 2) | int(lv, 2)
        result = f"{result:0{width}b}"
        return result

    def ast_xor(self,rv,lv,width:int):
        result = int(rv, 2) ^ int(lv, 2)
        result = f"{result:0{width}b}"
        return result

    def ast_add(self,rv,lv,width:int):
        if rv[0] == "1":
            rv = "-0b"+rv
        if lv[0] == "1":
            lv = "-0b"+lv
        result = int(rv, 2) + int(lv, 2)
        result = f"{result:0{width}b}"
        result = format(result & int("1"*width,2),f"{width}b")
        return result

    def ast_sub(rv,lv,width:int):
        if rv[0] == "1":
            rv = "-0b"+rv
        if lv[0] == "1":
            lv = "-0b"+lv
        result = int(rv, 2) - int(lv, 2)
        result = f"{result:0{width}b}"
        result = format(result & int("1"*width,2),f"{width}b")
        return result

    def ast_muls(rv,lv,width:int):
        if rv[0] == "1":
            rv = "-0b"+rv
        if lv[0] == "1":
            lv = "-0b"+lv
        result = int(rv, 2) * int(lv, 2)
        result = f"{result:0{width}b}"
        result = format(result & int("1"*width,2),f"{width}b")
        return result

    def ast_eq(rv,lv,width:int):
        if rv == lv:
            return "1"
        else:
            return "0"

    def ast_neq(rv,lv,width:int):
        if rv != lv:
            return "1"
        else:
            return "0"

    def ast_not(iv):
        result = ""
        for c in iv:
            if c == "1":
                result = result + "0"
            else:
                result = result + "1"
        return result


    def ast_concat(rv,lv):
        return rv+lv

    #def eq_len(x:str,y:str):
    #    return len(x) == len(y)

    #def check_eq_len(x:str,y:str):
    #    if not self.eq_len(x,y):
    #        raise 

    def assign(self,node):
        pass

class Simulator(Simulator_Compute):
    def __init__(self,ast):
        Simulator_Compute.__init__(self,ast)

    def simulate(self):
        t_set = set()
        for node in self.ast_node_list:
            t_set.add(type(node))
        print(t_set)
        for subcircuit_id in self.ordered_subcircuit_id_head:
            entry_id = self._map__subcircuit_id_2_ast_id[subcircuit_id]
            entry_node = self.get_node(entry_id)
            self.execute(entry_node)
        for subcircuit_id in self.ordered_subcircuit_id_tail:
            entry_id = self._map__subcircuit_id_2_ast_id[subcircuit_id]
            entry_node = self.get_node(entry_id)
            self.execute(entry_node)




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
    ast_sim = Simulator(ast)
    ast_sim.convert()
    ast_sim.simulate()

