from AST_Checker import *
from AST_NodeClassify import *

import pprint
from copy import deepcopy
import pandas as pd
import json








class AST_Schedule_Preprocess:
    def __init__(self,ast):
        self._ast = ast

    def merge_multi_name_var(self):
        # Merge the <varref> that have different names but refer to same signal
        # Unify their names
        print("[AST Schedule Preprocess] start merging multi-named signals...")
        signal_merge_dict = dict()
        signal_buckets = list()

        analyzer = AST_Analyzer(self._ast)
        input_set = set(analyzer.get_input_port())
        lv_signal_set = set(analyzer.get_lv())

        all_signal_set = input_set | lv_signal_set

        for assignalias in self._ast.findall(".//topscope//assignalias"):
            v1 = assignalias.getchildren()[0].attrib["name"]
            v2 = assignalias.getchildren()[1].attrib["name"]
            bucket_idx = [i for i,s in enumerate(signal_buckets) if (v1 in s or v2 in s)]
            bucket_idx = bucket_idx if bucket_idx == [] else bucket_idx[0]
            if bucket_idx == []:
                i = len(signal_buckets)
                signal_buckets.append(set())
                signal_buckets[i].add(v1)
                signal_buckets[i].add(v2)
            else:
                signal_buckets[bucket_idx].add(v1)
                signal_buckets[bucket_idx].add(v2)
        for i,s in enumerate(signal_buckets):
            main_signal = [v for v in s if v in all_signal_set][0]
            signal_merge_dict[main_signal] = s

        # Merging Node with Same Name
        for main_sig in signal_merge_dict:
            self._show_merge_info(main_sig,signal_merge_dict[main_sig])
            for sig in signal_merge_dict[main_sig]:
                # Remove <varscope>
                if sig != main_sig:
                    for varref in self._ast.findall(f".//varref[@name='{sig}']"):
                        varref.attrib["name"] = main_sig
                    varscope = self._ast.find(f".//topscope//varscope[@name='{sig}']")
                    self._remove_ast_node(varscope)
                    var = self._ast.find(f".//var[@name='{sig}']")
                    self._remove_ast_node(var)
        print("-"*80)

    def _show_merge_info(self,main_sig, merge_sig):
        indent = len(f"  - merging: {main_sig} <= ")
        for idx, sig in enumerate(merge_sig):
            if idx == 0:
                print(f"  - merging: {main_sig} <= {sig}")
            else:
                print(" "*indent+f"{sig}")
        print()


    def merge_initial_var_const(self):
        for init_assign in self._ast.findall(".//initial/assign"):
            lv_node = init_assign.getchildren()[1]
            lv_name = lv_node.attrib["name"]
            rv_node = init_assign.getchildren()[0]
            for varref in self._ast.findall(f".//varref[@name='{lv_name}']"):
                varref.getparent().replace(varref,rv_node)
            for var in self._ast.findall(f".//var[@name='{lv_name}']"):
                self._remove_ast_node(var)
            for varscope in self._ast.findall(f".//topscope//varscope[@name='{lv_name}']"):
                self._remove_ast_node(varscope)

    def remove_initial(self):
        for initial in self._ast.findall(".//initial"):
            self._remove_ast_node(initial)

    def proc(self):
        self.preprocess()

    def preprocess(self):
        checker = AST_Checker(self._ast)
        checker.check_simple_design()

        self.remove_comment_node()
        self.remove_empty_initial()
        self.remove_param_var()

        self.merge_multi_name_var()
        self.merge_initial_var_const()

        self.mark_var_sig_type()
        self.mark_comb_subcircuit_lv_name()

        self.numbering_subcircuit()
        self.numbering_assignment()
        self.numbering_circuit_node()

        self.modify_full_case()
        self.modify_full_if()


    def remove_comment_node(self):
        for comment in self._ast.findall(".//comment"):
            self._remove_ast_node(comment)

    def remove_empty_initial(self):
        for initial in self._ast.findall(".//initial"):
            if len(initial.getchildren()) == 0:
                self._remove_ast_node(initial)


    def remove_param_var(self):
        for var in self._ast.findall(".//var"):
            if "param" in var.attrib:
                self._remove_ast_node(var)
            elif "localparam" in var.attrib:
                self._remove_ast_node(var)


    def mark_var_sig_type(self):
        register_name_set = set(self.find_register_var())
        for var in self._ast.findall(".//var"):
            var_name = var.attrib["name"]
            if var_name in register_name_set:
                var.attrib["sig_type"] = "register"
            else:
                var.attrib["sig_type"] = "wire"

    def mark_comb_subcircuit_lv_name(self):
        self.mark_wireassign_lv_name()
        self.mark_comb_always_lv_name()

    def mark_wireassign_lv_name(self):
        for contassign in self._ast.findall(".//contassign"):
            lv_node = contassign.getchildren()[1]
            lv_sig_name = AST_Analyzer.get_sig_name(lv_node)
            contassign.attrib["lv_name"] = lv_sig_name

    def mark_comb_always_lv_name(self):
        for always in self._ast.findall(".//always"):
            if always.find(".//sentree") != None:
                continue
            assign = always.find(".//assign")
            lv_node = assign.getchildren()[1]
            lv_sig_name = AST_Analyzer.get_sig_name(lv_node)
            always.attrib["lv_name"] = lv_sig_name

    #def _get_lv_sig_name(self,node):
    #    if node.tag == "varref":
    #        sig_name = node.attrib["name"]
    #        return sig_name
    #    elif node.tag == "sel" or node.tag == "arraysel":
    #        return AST_Analyzer.get_sig_name(node.getchildren()[0])
    #    else:
    #        raise Unconsidered_Case("",0)

    def numbering_subcircuit(self):
        print("[AST Schedule Preprocess] start numbering subcircuits...")
        self.subcircuit_num = 0
        for sub_circuit in self._ast.findall(".//contassign") + self._ast.findall(".//always"):
            sub_circuit.attrib["subcircuit_id"] = str(self.subcircuit_num)
            self.subcircuit_num += 1
        print(f"  - finished. total number of subcircuit = {self.subcircuit_num}")
        print("-"*80)

    def numbering_assignment(self):
        print("[AST Schedule Preprocess] start numbering assignment...")
        self.assignment_num = 0
        for assign in self._ast.findall(".//contassign") + self._ast.findall(".//always//assign") + self._ast.findall(".//always//assigndly"):
            assign.attrib["assignment_id"] = str(self.assignment_num)
            self.assignment_num += 1
        print(f"  - finished. total number of assignment = {self.assignment_num}")
        print("-"*80)


    def numbering_circuit_node(self):
        print("[AST Schedule Preprocess] start numbering circuit node...")
        self.circuit_node_num = 0
        self.numbering_var_node()
        self.numbering_ctrl_node()
        self.numbering_op_node()
        print(f"  - finished. total number of circuit node = {self.circuit_node_num}")
        print("-"*80)

    def numbering_var_node(self):
        for var in self._ast.findall(".//module//var"):
            var.attrib["circuit_node_id"] = str(self.circuit_node_num)
            var_name = var.attrib["name"]
            # Also give node id to all of its <varref>
            for varref in self._ast.findall(f".//varref[@name='{var_name}']"):
                varref.attrib["circuit_node_id"] = str(self.circuit_node_num)
            self.circuit_node_num += 1

    def numbering_ctrl_node(self):
        for if_node in self._ast.findall(".//always//if"):
            ctrl_node = if_node.getchildren()[0]
            for node in ctrl_node.iter():
                if node.tag != "varref":
                    node.attrib["circuit_node_id"] = str(self.circuit_node_num)
                    self.circuit_node_num += 1

    def numbering_op_node(self):
        for assign in self._ast.findall(".//contassign") + self._ast.findall(".//always//assign") + self._ast.findall(".//always//assigndly"):
            for node in assign.iter():
                if (not "assign" in node.tag) and node.tag != "varref":
                    node.attrib["circuit_node_id"] = str(self.circuit_node_num)
                    self.circuit_node_num += 1

    def modify_full_case(self):
        for case_node in self._ast.findall(".//always//case"):
            last_caseitem = case_node.getchildren()[-1]
            if AST_Checker.node_has_child(last_caseitem):
                if "circuit_node_id" in last_caseitem.getchildren()[0].attrib:
                    new_node = etree.Element("caseitem")
                    case_node.append(new_node)


    def modify_full_if(self):
        for if_node in self._ast.findall(".//always//if"):
            if len(if_node.getchildren()) < 3:
                new_node = etree.Element("begin")
                if_node.append(new_node)
    
    def find_register_var(self):
        analyzer = AST_Analyzer(self._ast)
        return analyzer.get_ff()

    def find_input_var(self):
        analyzer = AST_Analyzer(self._ast)
        return analyzer.get_input_port()

    def _find_dst_var_node(self,lv_node):
        if lv_node.tag == "arraysel" or lv_node.tag == "sel":
            target_node = lv_node.getchildren()[0]
            return self._find_dst_var_node(target_node)
        elif lv_node.tag == "varref":
            return lv_node
        else:
            raise Unconsidered_Case(f"node tag = {lv_node.tag}",0)


class AST_Schedule_Subcircuit(AST_Schedule_Preprocess):
    def __init__(self,ast):
        AST_Schedule_Preprocess.__init__(self,ast)

    def proc(self):
        self.preprocess()
        self.schedule_subcircuit()

    def schedule_subcircuit(self):
        self._ast_schedule = deepcopy(self._ast)
        self.subcircuit_id_list = [subcircuit_id for subcircuit_id in range(self.subcircuit_num)]
        self.ordered_subcircuit_id_list = []
        self.ordered_subcircuit_id_tail = []
        self.ordered_subcircuit_id_head = []

        self._schedule_ff_always()
        self._schedule_comb_subcircuit()
        print(f"finished. total scheduled subcircuit number = {len(self.ordered_subcircuit_id_list)}")

    def _schedule_ff_always(self):
        for always in self._ast_schedule.findall(".//always"):
            if always.find(".//sentree") == None:
                continue
            subcircuit_id = int(always.attrib["subcircuit_id"])
            self.subcircuit_id_list.remove(subcircuit_id)
            self.ordered_subcircuit_id_tail.append(subcircuit_id)

    def _schedule_comb_subcircuit(self):
        self._remove_comb_dst_var_node()
        self._remove_ctrl_register()
        self._remove_src_register()
        self._remove_ctrl_input_port()
        self._remove_src_input_port()
        self._remove_comb_lv_on_the_right()
        while(self.subcircuit_id_list != []):
            new_ready_subcircuit_list = self._find_ready_subcircuit()
            self._update_ready_node(new_ready_subcircuit_list)
            self._remove_ready_node(new_ready_subcircuit_list)

        self.ordered_subcircuit_id_head = self.ordered_subcircuit_id_list
        self.ordered_subcircuit_id_list = self.ordered_subcircuit_id_list + self.ordered_subcircuit_id_tail
        self.output()

    def output(self):
        with open("output.xml","w") as fp:
            fp.write(etree.tostring(self._ast_schedule.find("."),pretty_print=True).decode())

    def _find_ready_subcircuit(self):
        new_ready_subcircuit_list = []
        for subcircuit_id in self.subcircuit_id_list:
            subcircuit = self._ast_schedule.find(f".//*[@subcircuit_id='{str(subcircuit_id)}']")
            if subcircuit.tag == "always" and subcircuit.find(".//sentree") != None:
                continue
            if subcircuit.find(".//varref") == None:
                subcircuit_id = int(subcircuit.attrib["subcircuit_id"])
                lv_name = subcircuit.attrib["lv_name"]
                new_ready_subcircuit_list.append((subcircuit_id,lv_name))
        return new_ready_subcircuit_list

    def _update_ready_node(self,ready_subcircuit_list):
        ready_subcircuit_id_list = [ready_subcircuit[0] for ready_subcircuit in ready_subcircuit_list]
        for ready_subcircuit_id in ready_subcircuit_id_list:
            self.subcircuit_id_list.remove(ready_subcircuit_id)
            self.ordered_subcircuit_id_list.append(ready_subcircuit_id)

    def _remove_ready_node(self,ready_subcircuit_list):
        ready_sig_name_set = set([ready_subcircuit[1] for ready_subcircuit in ready_subcircuit_list])
        for subcircuit_id in self.subcircuit_id_list:
            subcircuit = self._ast_schedule.find(f".//*[@subcircuit_id='{subcircuit_id}']")
            for varref in subcircuit.findall(".//varref"):
                var_name = varref.attrib["name"]
                if var_name in ready_sig_name_set:
                    self._remove_ast_node(varref)
    
    def _remove_ast_node(self,node):
        node.getparent().remove(node)

    def _remove_comb_dst_var_node(self):
        for assign in self._ast_schedule.findall(".//contassign") + self._ast_schedule.findall(".//always//assign"):
            lv_node = assign.getchildren()[1]
            dst_var_node = self._find_dst_var_node(lv_node)
            self._remove_ast_node(dst_var_node)

    def _remove_ctrl_input_port(self):
        input_name_set = set(self.find_input_var())
        for input_name in input_name_set:
            for varref in self._ast_schedule.findall(f".//always//varref[@name='{input_name}']"):
                if not "assign" in self._ast_schedule.getpath(varref):
                    self._remove_ast_node(varref)

    def _remove_src_input_port(self):
        input_name_set = set(self.find_input_var())
        for assign in self._ast_schedule.findall(".//contassign") + self._ast_schedule.findall(".//always//assign"):
            for varref in assign.findall(".//varref"):
                var_name = varref.attrib["name"]
                if var_name in input_name_set:
                    self._remove_ast_node(varref)

    def _remove_ctrl_register(self):
        register_name_set = set(self.find_register_var())
        for register_name in register_name_set:
            for varref in self._ast_schedule.findall(f".//always//varref[@name='{register_name}']"):
                if not "assign" in self._ast_schedule.getpath(varref):
                    self._remove_ast_node(varref)

    def _remove_src_register(self):
        register_name_set = set(self.find_register_var())
        for assign in self._ast_schedule.findall(".//contassign") + self._ast_schedule.findall(".//always//assign"):
            for varref in assign.findall(".//varref"):
                var_name = varref.attrib["name"]
                if var_name in register_name_set:
                    self._remove_ast_node(varref)

    def _remove_comb_lv_on_the_right(self):
        for always in self._ast_schedule.findall(".//always"):
            if always.find(".//sentree") != None:
                continue
            lv_name = always.attrib["lv_name"]
            for varref in always.findall(f".//varref[@name='{lv_name}']"):
                self._remove_ast_node(varref)

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


from abc import ABC, abstractmethod

# Define the RTL Circuit Graph Node Data Structure
class CFG_Base_Node:
    def __init__(self):
        pass

    @abstractmethod
    def tag(self):
        pass

    @property
    def cfg_id(self):
        return self.__cfg_id

    @cfg_id.setter
    def cfg_id(self,cfg_id:int):
        if cfg_id < 0:
            raise ValueError("cfg ID cannot be negative")
        else:
            self.__cfg_id = cfg_id

class CFG_One_Child_Node(CFG_Base_Node):
    def __init__(self):
        CFG_Base_Node.__init__(self)

    @property
    def child_id(self):
        return self.__child_id

    @child_id.setter
    def child_id(self,value:int):
        self.__child_id = value


class CFG_Entry_Node(CFG_One_Child_Node):
    def __init__(self):
        CFG_One_Child_Node.__init__(self)

    @property
    def subcircuit_id(self):
        return self.__subcircuit_id

    @subcircuit_id.setter
    def subcircuit_id(self,value:int):
        self.__subcircuit_id = value

    @property
    def tag(self):
        return "entry"


class CFG_End_Node(CFG_Base_Node):
    def __init__(self):
        CFG_Base_Node.__init__(self)

    @property
    def tag(self):
        return "end"

class CFG_Branch_Node(CFG_Base_Node):
    def __init__(self):
        CFG_Base_Node.__init__(self)
        self._ctrl_node_id

class CFG_IF_Node(CFG_Branch_Node):
    def __init__(self):
        CFG_Branch_Node.__init__(self)

    @property
    def true_child_id(self):
        return self.__true_child_id

    @true_child_id.setter
    def true_child_id(self,value:int):
        self.__true_child_id = value

    @property
    def false_child_id(self):
        return self.__false_child_id

    @false_child_id.setter
    def false_child_id(self,value:int):
        self.__false_child_id = value

    @property
    def tag(self):
        return "if"

class CFG_CASE_Node(CFG_Branch_Node):
    def __init__(self):
        CFG_Branch_Node.__init__(self)

    @property
    def tag(self):
        return "case"

class CFG_Assign_Node(CFG_One_Child_Node):
    def __init__(self, assignment_id:int):
        CFG_One_Child_Node.__init__(self)
        self.__assignment_id = assignment_id

    @property
    def tag(self):
        return "assign"

    @property
    def assignment_id(self,value:int):
        return self.__assignment_id
        
    

class AST_Construct_CFGraph(AST_Schedule_Subcircuit):
    def __init__(self,ast):
        AST_Schedule_Subcircuit.__init__(self,ast)

    def proc(self):
        self.preprocess()
        self.schedule_subcircuit()
        self.construct_cfg_proc()


    def construct_cfg_proc(self):
        self.cfg_list = []
        self.cfg_entry = []
        for subcircuit_id in range(self.subcircuit_num):
            subcircuit = self._ast.find(f".//*[@subcircuit_id='{str(subcircuit_id)}']")
            self._construct_cfg(subcircuit)
    

    def _construct_cfg(self, node, pre_tail = None):
        if node.tag == "always":
            self._add_cfg_entry_node(new_node)
            self._add_cfg_node(new_node)

            self.cfg_list.append()
            if node.getchildren()[0].tag == "sentree":
                for child in node.getchildren()[1:]:
                    self._construct_cfg(child)
            else:
                for child in node.getchildren():
                    self._construct_cfg(child)
        elif node.tag == "contassign":
            self._add_cfg_assign_node(pre_tail)
            
        else:
            if node.tag == "if":
                new_if_tail = self._add_cfg_if_node(pre_tail)
                true_tail = [new_if_tail[0]]
                false_tail = [new_if_tail[1]]
                new_tail = []
                new_tail += self._construct_cfg(node.getchilren()[1], true_tail)
                new_tail += self._construct_cfg(node.getchilren()[2], true_tail)
            elif node.tag == "case":
                pass
            elif node.tag == "begin":
                for child in node.getchildren():
                    pre_tail = self._construct_cfg(child, pre_tail)
                return pre_tail
            elif node.tag == "caseitem":
                n_pre_tail = pre_tail

                # Get the index of first statement
                first_statement_id = None
                for idx, child in enumerate(node.getchildren()):
                    if not "circuit_node_id" in child.attrib:
                        first_statement_id = idx
                        break

                if first_statement_id != None:
                    children = node.getchildren()[first_statement_id:]
                else:
                    children = []

                for child in children:
                    n_pre_tail = self._construct_cfg(child, n_pre_tail)
                return n_pre_tail

                    




            elif node.tag == "assign" or node.tag == "assigndly":
                return self._add_cfg_assign_node(pre_tail)
            else:
                print("Error: Unknown false_tailCFG Node.")
                pass


    def _add_cfg_if_node(self,pre_tail:list):
        new_node = CFG_IF_Node()
        new_node.cfg_id = len(self.cfg_list)
        true_tail = self._add_cfg_entry_node()
        false_tail = self._add_cfg_entry_node()
        return [true_tail, false_tail]



    def _add_cfg_entry_node(self):
        new_node = CFG_Entry_Node()
        new_node.cfg_id = len(self.cfg_list)
        self.cfg_list.append(new_node)
        return [new_node.cfg_id]

    def _add_cfg_assign_node(self,pre_tail:list):
        new_node = CFG_Assign_Node()
        new_node.cfg_id = len(self.cfg_list)
        for tail_id in pre_tail:
            self.cfg_list[tail_id].child_id(new_node.cfg_id)
        self.cfg_list.append(new_node)
        return [new_node.cfg_id]




if __name__ == "__main__":
    # Step 1: Create the parser
    parser = argparse.ArgumentParser(description="A simple example of argparse usage.")

    # Step 2: Define arguments
    parser.add_argument("ast", type=str, help="AST path")                  # Positional argument

    # Step 3: Parse the arguments
    args = parser.parse_args()

    ast_file = args.ast
    ast = Verilator_AST_Tree(ast_file)

    ast_scheduler = AST_Schedule_Subcircuit(ast)
    ast_scheduler.proc()


