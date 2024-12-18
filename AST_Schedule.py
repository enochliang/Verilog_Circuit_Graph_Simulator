from AST_Checker import *
from AST_NodeClassify import *

import pprint
from copy import deepcopy
import json

class AST_Remove_Node:
    def __init__(self,ast):
        self._ast = ast

    def remove_initial(self):
        for initial in self._ast.findall(".//initial"):
            self._remove_ast_node(initial)

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

    def remove_sentree(self):
        for always in self._ast.findall(".//always"):
            sentree = always.find(".//sentree")
            if sentree != None:
                self._remove_ast_node(sentree)


class AST_Merge_Node(AST_Remove_Node):
    def __init__(self,ast):
        AST_Remove_Node.__init__(self,ast)

    def merge_multi_name_var(self):
        # Merge the <varref> that have different names but refer to same signal
        # Unify their names
        print("[AST Schedule Preprocess] start merging multi-named signals...")
        signal_merge_dict = dict()
        signal_buckets = list()

        analyzer = AST_Analyzer(self._ast)
        input_set = set(analyzer.get_sig__input_port())
        lv_signal_set = set(analyzer.get_sig__lv())

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


class AST_Mark_Info(AST_Merge_Node):
    def __init__(self,ast):
        AST_Merge_Node.__init__(self,ast)

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
            lv_sig_name = AST_Analysis_Function.get_sig_name(lv_node)
            contassign.attrib["lv_name"] = lv_sig_name

    def mark_comb_always_lv_name(self):
        for always in self._ast.findall(".//always"):
            if always.find(".//sentree") != None:
                continue
            assign = always.find(".//assign")
            lv_node = assign.getchildren()[1]
            lv_sig_name = AST_Analysis_Function.get_sig_name(lv_node)
            always.attrib["lv_name"] = lv_sig_name

    def mark_always_type(self):
        for always in self._ast.findall(".//always"):
            if always.find(".//sentree") != None:
                always.attrib["type"] = "ff"
            else:
                always.attrib["type"] = "comb"

    def mark_width(self):
        dtypeid_2_width_dict = AST_Analysis_Function.get_dict__dtypeid_2_width(self._ast)
        for node in self._ast.iter():
            if "dtype_id" in node.attrib:
                dtype_id = node.attrib["dtype_id"]
                node.attrib["width"] = str(dtypeid_2_width_dict[dtype_id])

class AST_Numbering(AST_Mark_Info):
    def __init__(self,ast):
        AST_Mark_Info.__init__(self,ast)

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


class AST_Schedule_Preprocess(AST_Numbering):
    def __init__(self,ast):
        AST_Numbering.__init__(self,ast)

    def proc(self):
        self.preprocess()

    def preprocess(self):
        checker = AST_Checker(self._ast)
        checker.check_simple_design()

        #self.add_array_node()

        self.remove_comment_node()
        self.remove_empty_initial()
        self.remove_param_var()

        self.merge_multi_name_var()
        self.merge_initial_var_const()

        self.mark_var_sig_type()
        self.mark_comb_subcircuit_lv_name()
        self.mark_always_type()
        self.mark_width()

        self.remove_sentree()

        self.numbering_subcircuit()
        #self.numbering_assignment()
        #self.numbering_circuit_node()

    def find_register_var(self):
        return AST_Analysis_Function.get_sig__ff(self._ast)

    def find_input_var(self):
        return AST_Analysis_Function.get_sig__input_port(self._ast)

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
        total_ast_node = 0
        for var in self._ast.findall(".//var"):
            total_ast_node += 1

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
        for always in self._ast_schedule.findall(".//always[@type='ff']"):
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
            if subcircuit.tag == "always" and subcircuit.attrib["type"] == "ff":
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
        for always in self._ast_schedule.findall(".//always[@type='comb']"):
            lv_name = always.attrib["lv_name"]
            for varref in always.findall(f".//varref[@name='{lv_name}']"):
                self._remove_ast_node(varref)

class AST_Schedule(AST_Schedule_Subcircuit):
    def __init__(self,ast):
        AST_Schedule_Subcircuit.__init__(self,ast)
    


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
    print(ast_scheduler.ordered_subcircuit_id_head)
    print(ast_scheduler.ordered_subcircuit_id_tail)


