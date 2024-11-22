from AST_Checker import *
from AST_NodeClassify import *

import pprint
from copy import deepcopy
import pandas as pd
import json


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


# Define the RTL Circuit Graph Node Data Structure
class Ctrl_Flow_Graph_Node:
    def __init__(self,name:str,width:int,value:str,node_type:str,fault_list:dict):
        self.name = name # "branch", "code_block"
        self.node_type = node_type # "if", "case", "code_block"
        self.ctrl_sig = ""
        self.statement_list = []

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

class AST_Schedule(AST_NodeClassify):
    def __init__(self,ast):
        AST_NodeClassify.__init__(self)
        self._ast = ast

    def merge_aliased_var(self):
        # Merge the <varref> that have different names but refer to same signal
        # Unify their names
        print("Start Merging Multi-named Signals...")
        idx = 0
        signal_num_dict = dict()
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
            print(f"    Merge: {main_sig} <= {signal_merge_dict[main_sig]}")
            for sig in signal_merge_dict[main_sig]:
                # Remove <varscope>
                if sig != main_sig:
                    for varref in self._ast.findall(f".//varref[@name='{sig}']"):
                        varref.attrib["name"] = main_sig
                    varscope = self._ast.find(f".//topscope//varscope[@name='{sig}']")
                    self._remove_ast_node(varscope)
                    var = self._ast.find(f".//var[@name='{sig}']")
                    self._remove_ast_node(var)

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

    def preprocess(self):
        checker = AST_Checker(self._ast)
        checker.check_simple_design()

        self.remove_comment_node()
        self.remove_empty_initial()
        self.remove_param_var()

        self.merge_aliased_var()
        self.merge_initial_var_const()

        self.mark_var_sig_type()
        self.mark_comb_subcircuit_lv_name()

        self.numbering_subcircuit()
        self.numbering_assignment()
        self.numbering_circuit_node()

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

    def find_register_var(self):
        analyzer = AST_Analyzer(self._ast)
        return analyzer.get_ff()

    def find_input_var(self):
        analyzer = AST_Analyzer(self._ast)
        return analyzer.get_input_port()

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
            lv_sig_name = self._get_lv_sig_name(lv_node)
            contassign.attrib["lv_name"] = lv_sig_name

    def mark_comb_always_lv_name(self):
        for always in self._ast.findall(".//always"):
            if always.find(".//sentree") != None:
                continue
            assign = always.find(".//assign")
            lv_node = assign.getchildren()[1]
            lv_sig_name = self._get_lv_sig_name(lv_node)
            always.attrib["lv_name"] = lv_sig_name



    def _get_lv_sig_name(self,node):
        if node.tag == "varref":
            sig_name = node.attrib["name"]
            return sig_name
        elif node.tag == "sel" or node.tag == "arraysel":
            return self._get_lv_sig_name(node.getchildren()[0])
        else:
            raise Unconsidered_Case("",0)

    def numbering_subcircuit(self):
        print("start numbering subcircuits...")
        self.subcircuit_num = 0
        for sub_circuit in self._ast.findall(".//contassign") + self._ast.findall(".//always"):
            sub_circuit.attrib["subcircuit_id"] = str(self.subcircuit_num)
            self.subcircuit_num += 1
        print(f"finished. total number of subcircuit = {self.subcircuit_num}")

    def numbering_assignment(self):
        print("start numbering assignment...")
        self.assignment_num = 0
        for assign in self._ast.findall(".//contassign") + self._ast.findall(".//always//assign") + self._ast.findall(".//always//assigndly"):
            assign.attrib["assignment_id"] = str(self.assignment_num)
            self.assignment_num += 1
        print(f"finished. total number of assignment = {self.assignment_num}")


    def numbering_circuit_node(self):
        print("start numbering circuit node...")
        self.circuit_node_num = 0
        self.numbering_var_node()
        self.numbering_ctrl_node()
        self.numbering_op_node()
        print(f"finished. total number of circuit node = {self.circuit_node_num}")

    def numbering_var_node(self):
        for var in self._ast.findall("var"):
            var.attrib["circuit_node_id"] = str(self.circuit_node_num)
            # Also give node id to all of its <varref>
            for varref in self._ast.findall(f"varref[@circuit_node_id='{str(self.circuit_node_num)}']"):
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
                if not "assign" in node.tag:
                    node.attrib["circuit_node_id"] = str(self.circuit_node_num)
                    self.circuit_node_num += 1


    def schedule(self):
        self.preprocess()
        self.schedule_subcircuit()

    def schedule_subcircuit(self):
        self._ast_schedule = deepcopy(self._ast)
        self.subcircuit_id_list = [subcircuit_id for subcircuit_id in range(self.subcircuit_num)]
        self.ordered_subcircuit_id_list = []
        self.ordered_subcircuit_id_tail = []

        self._schedule_ff_always()
        self._schedule_comb_subcircuit()
        print(len(self.ordered_subcircuit_id_list))

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

        
        self.ordered_subcircuit_id_list = self.ordered_subcircuit_id_list + self.ordered_subcircuit_id_tail

    def output(self):
        with open("output.xml","wb") as fp:
            fp.write(etree.tostring(self._ast_schedule.find(".")))
    
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


    def _find_dst_var_node(self,lv_node):
        if lv_node.tag == "arraysel" or lv_node.tag == "sel":
            target_node = lv_node.getchildren()[0]
            return self._find_dst_var_node(target_node)
        elif lv_node.tag == "varref":
            return lv_node
        else:
            raise Unconsidered_Case(f"node tag = {lv_node.tag}",0)



if __name__ == "__main__":
    # Step 1: Create the parser
    parser = argparse.ArgumentParser(description="A simple example of argparse usage.")

    # Step 2: Define arguments
    parser.add_argument("ast", type=str, help="AST path")                  # Positional argument

    # Step 3: Parse the arguments
    args = parser.parse_args()

    ast_file = args.ast
    ast = Verilator_AST_Tree(ast_file)

    ast_scheduler = AST_Schedule(ast)
    ast_scheduler.schedule()


