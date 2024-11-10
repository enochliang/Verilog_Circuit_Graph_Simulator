from AST_2CircuitGraph import *

import pprint
from copy import deepcopy
import pandas as pd
import json

class SimulationError(Exception):
    def __init__(self, message, error_code):
        super().__init__(message)
        self.error_code = error_code

    def __str__(self):
        return f"{self.args[0]} (Error Code: {self.error_code})"

def gt_propagate_prob_mul_bit(var:str,cnst:str):
    #   var > const
    # !(var <= const)
    width = len(var)
    var_range = pow(2,width)
    if int(var,2) > int(cnst,2):
        prob = float(int(cnst,2) + 1) / float(var_range)
    else:
        prob = float(var_range - int(cnst,2) - 1) / float(var_range)
    return prob


def lt_propagate_prob_mul_bit(var:str,cnst:str):
    #   var < const
    # !(var >= const)
    width = len(var)
    var_range = pow(2,width)
    if int(var,2) < int(cnst,2):
        prob = float(int(cnst,2)) / float(var_range)
    else:
        prob = float(var_range - int(cnst,2)) / float(var_range)
    return prob

def eq_propagate_prob_mul_bit(var:str,cnst:str):
    #   var == const
    # !(var != const)
    width = len(var)
    var_range = pow(2,width)
    if int(var,2) == int(cnst,2):
        prob = float(var_range - 1) / float(var_range)
    else:
        prob = float(1.0) / float(var_range)
    return prob

class RTL_Simulator(AST_NodeClassify):
    def __init__(self):
        AST_NodeClassify.__init__(self)
        ast = Verilator_AST_Tree("./ast/Vsha1.xml")
        sim = AST_2CircuitGraph(ast)
        sim.build_simulator()
        self.circuit_graph_node, self.circuit_graph_edge = sim.get_circuit_graph()
        self.circuit_graph_edge_grouped = [None]*len(self.circuit_graph_node)
        cur_id = None
        cur_edges = []
        for edge in self.circuit_graph_edge:
            if cur_id == edge[0]:
                cur_edges.append(edge)
            else:
                if cur_id != None:
                    self.circuit_graph_edge_grouped[cur_id] = cur_edges
                cur_id = edge[0]
                cur_edges = [edge]
        self.circuit_graph_edge_grouped[cur_id] = cur_edges

        self.scheduled_node_num_list = sim.get_node_order()
        self.signal_table = sim.get_signal_table()
        self.cycle = 207

    def _load_logic_value(self):
        # Load Logic Values & Initialize Fault List
        f = open("graph_sig_dict.json","r")
        self.sig_dict = json.load(f)
        f.close()
        self.sig_dict.pop("clk")
        self.unknown_sig_list = [sig for sig in self.sig_dict.keys() if "__Vdfg" in sig]
        for sig in self.unknown_sig_list:
            self.sig_dict.pop(sig)

        f = open(f"../sha1/run_graph/pattern/FaultFree_Signal_Value_C{self.cycle:05}.txt","r")
        logic_values = f.readlines()
        for i,v in enumerate(logic_values):
            logic_values[i] = logic_values[i].replace("\n","")
        f.close()
        # Loading Logic Values
        for idx, sig in enumerate(self.sig_dict.keys()):
            width = int(self.signal_table[sig]["width"])
            node_id = int(self.signal_table[sig]["node_id"])
            if self.circuit_graph_node[node_id].width != width:
                # Check the Loaded Value Has Correct Width
                print("Error: width incorrect!!!")
            else:
                if self.circuit_graph_node[node_id].node_type == "FF_out":
                    sig_name = self.circuit_graph_node[node_id].name
                    self.circuit_graph_node[node_id].set_fault_list({sig_name:{"prob":1.0,"type":"data"}})
                if self.circuit_graph_node[node_id].node_type == "input":
                    self.circuit_graph_node[node_id].set_fault_list({"input":{"prob":1.0,"type":"data"}})
                self.circuit_graph_node[node_id].value = logic_values[idx]
                self.circuit_graph_node[node_id].ready_flag = True

        for node_id in range(len(self.circuit_graph_node)):
            if self.circuit_graph_node[node_id].name == "const":
                self.circuit_graph_node[node_id].set_fault_list({"const":{"prob":1.0,"type":"data"}})


    def _compute(self,node_id):
        name = self.circuit_graph_node[node_id].name
        edges = self.circuit_graph_edge_grouped[node_id]
        width = self.circuit_graph_node[node_id].width
        if name in self.sim_commutable_2in_op:
            a_id = edges[0][2]
            b_id = edges[1][2]
            a = self.circuit_graph_node[a_id].value
            b = self.circuit_graph_node[b_id].value
            # Check if all inputs are ready.
            if not (self.circuit_graph_node[a_id].ready_flag and self.circuit_graph_node[b_id].ready_flag):
                raise SimulationError(f"Error: Scheduling Incorrect. NODE_ID = {node_id}, OP_NAME = {name}",2)
           
            if name in {'xor','and','or','add','eq'}:
                if len(a) != len(b):
                    raise SimulationError(f"Error: Input Widths Don't Match. NODE_ID = {node_id}, OP_NAME = {name}",1)
            elif name in {'logor','logand'}:
                pass
            else:
                raise SimulationError(f"Error: Unrecognized OP Node! Node Name = {name}",1)

            # Compute OP Result
            if "x" in a or "x" in b:
                result = "x"*width
            elif "z" in a or "z" in b:
                result = "z"*width
            else:
                if name == 'xor':
                    result = int(a, 2) ^ int(b, 2)
                    result = f"{result:0{len(a)}b}"
                elif name == 'and':
                    result = int(a, 2) & int(b, 2)
                    result = f"{result:0{len(a)}b}"
                elif name == 'or':
                    result = int(a, 2) | int(b, 2)
                    result = f"{result:0{len(a)}b}"
                elif name == 'add':
                    result = int(a, 2) + int(b, 2)
                    result = f"{result:0{width}b}"
                    if self.circuit_graph_node[node_id].width != len(result):
                        result = result[len(result)-width:]
                elif name == 'eq':
                    result = "1" if a == b else "0"
                elif name == 'logor':
                    a = "1" if "1" in a else "0"
                    b = "1" if "1" in b else "0"
                    result = int(a,2) | int(b,2)
                    result = f"{result:0{width}b}"
                elif name == 'logand':
                    a = "1" if "1" in a else "0"
                    b = "1" if "1" in b else "0"
                    result = int(a,2) & int(b,2)
                    result = f"{result:0{width}b}"

            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        elif name in self.sim_not_commutable_2in_op:
            a_id = [edge[2] for edge in edges if edge[1] == "left"][0]
            b_id = [edge[2] for edge in edges if edge[1] == "right"][0]
            a = self.circuit_graph_node[a_id].value
            b = self.circuit_graph_node[b_id].value
            if not (self.circuit_graph_node[a_id].ready_flag and self.circuit_graph_node[b_id].ready_flag):
                raise SimulationError(f"Error: Scheduling Incorrect. NODE_ID = {node_id}, OP_NAME = {name}",2)
            if "x" in a or "x" in b:
                result = "x"*width
            elif "z" in a or "z" in b:
                result = "z"*width
            else:
                if name == 'gt':
                    result = "1" if int(a,2) > int(b,2) else "0"
                elif name == 'gte':
                    result = "1" if int(a,2) >= int(b,2) else "0"
                elif name == 'lt':
                    result = "1" if int(a,2) < int(b,2) else "0"
                elif name == 'lte':
                    result = "1" if int(a,2) <= int(b,2) else "0"
                elif name == 'concat':
                    result = a + b
            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        elif name in self.sim_1in_op:
            a_id = edges[0][2]
            a = self.circuit_graph_node[a_id].value
            if name == 'extend':
                result = "0"*(width - len(a)) + a
            elif name == 'not':
                mask = "1"*len(a)
                result = int(a,2) ^ int(mask,2)
                result = f"{result:0{width}b}"
            elif name == 'sel':
                bits = self.circuit_graph_node[node_id].attrib["bits"]
                bits = bits[1:-1].split(":")
                l_bit = int(bits[0])
                r_bit = int(bits[1])
                if l_bit == r_bit:
                    result = a[-1 - l_bit]
                elif r_bit == 0:
                    result = a[len(a)-1-l_bit:]
                else:
                    result = a[len(a)-1-l_bit:0-r_bit]
            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        elif name == 'const':
            self.circuit_graph_node[node_id].ready_flag = True
            return
        elif name == 'if' or name == 'if_ff':
            ctrl_id = [edge[2] for edge in edges if edge[1] == "ctrl"][0]
            ctrl = self.circuit_graph_node[ctrl_id].value
            if "x" in ctrl:
                ctrl = "x"
            elif "z" in ctrl:
                raise SimulationError(f"Error: ctrl = '{ctrl}'. NODE_ID = {node_id}, OP_NAME = {name}",2)
            else:
                ctrl = "1" if "1" in ctrl else "0"
            if "x" in ctrl:
                result = "x"*width
            else:
                tmp_edges = [edge[2] for edge in edges if edge[1] == ctrl]
                if tmp_edges == []: # The <if> is not fullcase
                    result = "z"*width
                    self._check_result_width(width,len(result))
                    self.circuit_graph_node[node_id].set_value(result)
                    self.circuit_graph_node[node_id].ready_flag = True
                    return
                src_id = [edge[2] for edge in edges if edge[1] == ctrl][0]
                result = self.circuit_graph_node[src_id].value
            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        elif name == 'case' or name == 'case_ff':
            ctrl_id = [edge[2] for edge in edges if edge[1] == "ctrl"][0]
            ctrl = self.circuit_graph_node[ctrl_id].value
            if "x" in ctrl:
                result = "x"*width
            elif "z" in ctrl:
                raise SimulationError(f"Error: ctrl = '{ctrl}'. NODE_ID = {node_id}, OP_NAME = {name}",2)
            else:
                tmp_edges = [edge[2] for edge in edges if edge[1] == ctrl]
                if tmp_edges == []:
                    tmp_edges = [edge[2] for edge in edges if edge[1] == "default"]
                    if tmp_edges == []: # The <case> is not fullcase
                        result = "z"*width
                        self._check_result_width(width,len(result))
                        self.circuit_graph_node[node_id].set_value(result)
                        self.circuit_graph_node[node_id].ready_flag = True
                        return
                src_id = tmp_edges[0]
                result = self.circuit_graph_node[src_id].value
            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        elif name == 'cond':
            ctrl_id = [edge[2] for edge in edges if edge[1] == "ctrl"][0]
            ctrl = self.circuit_graph_node[ctrl_id].value
            if "x" in ctrl:
                ctrl = "x"
            else:
                ctrl = "1" if "1" in ctrl else "0"

            if "x" in ctrl:
                result = "x"*width
            else:
                src_id = [edge[2] for edge in edges if edge[1] == ctrl][0]
                result = self.circuit_graph_node[src_id].value
            self._check_result_width(width,len(result))
            self.circuit_graph_node[node_id].set_value(result)
            self.circuit_graph_node[node_id].ready_flag = True
        else:
            self.circuit_graph_node[node_id].ready_flag = True
            print(f"Error: Unrecognized OP Node! Node Name = {name}")

    def _assign(self,node_id):
        name = self.circuit_graph_node[node_id].name
        edges = self.circuit_graph_edge_grouped[node_id]
        i_node_id = edges[0][2]
        value = self.circuit_graph_node[i_node_id].value
        if "x" in self.circuit_graph_node[node_id].value:
            self.circuit_graph_node[node_id].set_value(value)
        else:
            if self.circuit_graph_node[i_node_id].value != value:
                print("Warning: Computed Signal Values Don't Match Dumped Signal Values")
        self.circuit_graph_node[node_id].ready_flag = True
        if len(edges) != 1:
            raise SimulationError("Error: Signal assignment should only has 1 input.",1)

    def _check_result_width(self,a:int,b:int):
        if a != b:
            raise SimulationError("Error: Result Widths Don't Match.",1)
    
    # 
    def _sig_fault_propagate(self,node_id):
        edges = self.circuit_graph_edge_grouped[node_id]
        n_fault_list = {}
        src_node_ids = [edge[2] for edge in edges]
        for src_id in src_node_ids:
            src_fault_list = self.circuit_graph_node[src_id].fault_list
            for key in src_fault_list:
                n_fault_list[key] = src_fault_list[key]
        self.circuit_graph_node[node_id].set_fault_list(n_fault_list)

    # Fault Propagation with 1.0 probability
    def _op_fault_propagate(self,node_id):
        name = self.circuit_graph_node[node_id].name
        edges = self.circuit_graph_edge_grouped[node_id]
        n_fault_list = {}
        if name in {"if","cond","case","if_ff","case_ff"}:
            ctrl_id = [edge[2] for edge in edges if edge[1] == "ctrl"][0]
            ctrl = self.circuit_graph_node[ctrl_id].value
            tmp_edges = [edge[2] for edge in edges if edge[1] == ctrl]
            if tmp_edges == []:
                tmp_edges = [edge[2] for edge in edges if edge[1] == "default"]
            if tmp_edges == []:
                pass
            else:
                src_id = tmp_edges[0]
                src_fault_list = self.circuit_graph_node[src_id].fault_list
                for key in src_fault_list:
                    n_fault_list[key] = src_fault_list[key]
            ctrl_fault_list = self.circuit_graph_node[ctrl_id].fault_list
            for key in ctrl_fault_list:
                n_fault_list[key] = ctrl_fault_list[key]
        elif name == "const":
            pass
        else:
            src_node_ids = [edge[2] for edge in edges]
            for src_id in src_node_ids:
                src_fault_list = self.circuit_graph_node[src_id].fault_list
                for key in src_fault_list:
                    n_fault_list[key] = src_fault_list[key]
        self.circuit_graph_node[node_id].set_fault_list(n_fault_list)

    # Propagation Probability Calculation Algo
    def _op_prob_fault_propagate(self,node_id):
        name = self.circuit_graph_node[node_id].name
        width = self.circuit_graph_node[node_id].width
        edges = self.circuit_graph_edge_grouped[node_id]

        if name == "const":
            pass
        elif name in {"if","cond","case","if_ff","case_ff"}:
            n_fault_list = {}
            ctrl_id = [edge[2] for edge in edges if edge[1] == "ctrl"][0]
            ctrl = self.circuit_graph_node[ctrl_id].value
            tmp_edges = [edge[2] for edge in edges if edge[1] == ctrl]
            if tmp_edges == []:
                tmp_edges = [edge[2] for edge in edges if edge[1] == "default"]
            if tmp_edges == []:
                pass
            else:
                src_id = tmp_edges[0]
                # Propagate Fault List from source signal
                src_fault_list = self.circuit_graph_node[src_id].fault_list
                for key in src_fault_list:
                    n_fault_list[key] = {"prob":src_fault_list[key]["prob"], "type": src_fault_list[key]["type"]}
            # Propagate Fault List from control signal
            ctrl_fault_list = self.circuit_graph_node[ctrl_id].fault_list
            for key in ctrl_fault_list:
                if name in {"if_ff","case_ff"}:
                    if (key == "const" or key == "input"):
                        continue
                    else:
                        n_fault_list[key] = {"prob":ctrl_fault_list[key]["prob"], "type": "ctrl"}
                else:
                    n_fault_list[key] = {"prob":ctrl_fault_list[key]["prob"], "type": ctrl_fault_list[key]["type"]}
            self.circuit_graph_node[node_id].set_fault_list(n_fault_list)
        else:
            n_fault_list = {}
            if name in {"gt","lt","gte","lte"}:
                src_node_ids = [edge[2] for edge in edges]
                if "const" in [self.circuit_graph_node[node_id].name for node_id in src_node_ids]: # 1 Variable Compare
                    const_node_id = [node_id for node_id in src_node_ids if self.circuit_graph_node[node_id].name == "const"][0]
                    var_node_id = [node_id for node_id in src_node_ids if self.circuit_graph_node[node_id].name != "const"][0]
                    right_id = [edge[2] for edge in edges if edge[1] == "right"][0]
                    left_id = [edge[2] for edge in edges if edge[1] == "left"][0]
                    var_value = self.circuit_graph_node[var_node_id].value
                    cnst_value = self.circuit_graph_node[const_node_id].value
                    if left_id == var_node_id: # output = var ? const
                        if name in {"gt","lte"}:
                            prob = gt_propagate_prob_mul_bit(var_value,cnst_value)
                        else:
                            prob = lt_propagate_prob_mul_bit(var_value,cnst_value)
                    else:                      # output = const ? var
                        if name in {"lt","gte"}:
                            prob = gt_propagate_prob_mul_bit(var_value,cnst_value)
                        else:
                            prob = lt_propagate_prob_mul_bit(var_value,cnst_value)
                    src_fault_list = self.circuit_graph_node[var_node_id].fault_list
                    for key in src_fault_list:
                        if (key in n_fault_list) and src_fault_list[key]["prob"] * prob < n_fault_list[key]["prob"]:
                            continue
                        n_fault_list[key] = {"prob":src_fault_list[key]["prob"] * prob, "type": src_fault_list[key]["type"]}
                else:
                    raise SimulationError("Error: Comparator has not only 1 variable input.")
            elif name == "eq":
                src_node_ids = [edge[2] for edge in edges]
                if "const" in [self.circuit_graph_node[node_id].name for node_id in src_node_ids]: # 1 Variable Compare
                    const_node_id = [node_id for node_id in src_node_ids if self.circuit_graph_node[node_id].name == "const"][0]
                    var_node_id = [node_id for node_id in src_node_ids if self.circuit_graph_node[node_id].name != "const"][0]
                    var_value = self.circuit_graph_node[var_node_id].value
                    cnst_value = self.circuit_graph_node[const_node_id].value
                    prob = eq_propagate_prob_mul_bit(var_value,cnst_value)
                    src_fault_list = self.circuit_graph_node[var_node_id].fault_list
                    for key in src_fault_list:
                        if (key in n_fault_list) and src_fault_list[key]["prob"] * prob < n_fault_list[key]["prob"]:
                            continue
                        n_fault_list[key] = {"prob":src_fault_list[key]["prob"] * prob, "type": src_fault_list[key]["type"]}
                else:
                    raise SimulationError("Error: Comparator has not only 1 variable input.")
            else:
                if name in self.prob_always_prop:
                    prob = 1.0
                    src_node_ids_probs = [(edge[2],prob) for edge in edges]

                elif name == "and":
                    src_node_ids = [edge[2] for edge in edges]
                    node_id_1 = src_node_ids[0]
                    node_id_2 = src_node_ids[1]
                    num_of_1_node_1 = self.circuit_graph_node[node_id_1].value.count("1")
                    num_of_1_node_2 = self.circuit_graph_node[node_id_2].value.count("1")
                    prob_1 = float(num_of_1_node_2) / float(width)
                    prob_2 = float(num_of_1_node_1) / float(width)
                    src_node_ids_probs = [(node_id_1,prob_1),(node_id_2,prob_2)]

                elif name == "or":
                    src_node_ids = [edge[2] for edge in edges]
                    node_id_1 = src_node_ids[0]
                    node_id_2 = src_node_ids[1]
                    num_of_0_node_1 = self.circuit_graph_node[node_id_1].value.count("0")
                    num_of_0_node_2 = self.circuit_graph_node[node_id_2].value.count("0")
                    prob_1 = float(num_of_0_node_2) / float(width)
                    prob_2 = float(num_of_0_node_1) / float(width)
                    src_node_ids_probs = [(node_id_1,prob_1),(node_id_2,prob_2)]

                elif name == "logand":
                    if self.circuit_graph_node[node_id].value == "1":
                        src_node_ids_probs = []
                        src_node_ids = [edge[2] for edge in edges]
                        for src_id in src_node_ids:
                            if self.circuit_graph_node[src_id].value.count("1") == 1:
                                prob = 1.0 / float(self.circuit_graph_node[src_id].width)
                            else:
                                prob = 0.0
                            src_fault_list = self.circuit_graph_node[src_id].fault_list
                            for key in src_fault_list:
                                if (key in n_fault_list) and src_fault_list[key]["prob"] * prob < n_fault_list[key]["prob"]:
                                    continue
                                n_fault_list[key] = {"prob":src_fault_list[key]["prob"] * prob, "type": src_fault_list[key]["type"]}
                    else:
                        prob = 1.0
                        src_node_ids_probs = [(edge[2], prob) for edge in edges]
                elif name == "logor":
                    if self.circuit_graph_node[node_id].value == "0":
                        src_node_ids_probs = []
                        src_node_ids = [edge[2] for edge in edges]
                        for src_id in src_node_ids:
                            if self.circuit_graph_node[src_id].value.count("1") == 1:
                                prob = 1.0 / float(self.circuit_graph_node[src_id].width)
                            else:
                                prob = 0.0
                            src_node_ids_probs.append((src_id,prob))
                    else:
                        prob = 1.0
                        src_node_ids_probs = [(edge[2], prob) for edge in edges]

                elif name == "sel":
                    src_id = edges[0][2]
                    prob = 1.0
                    src_node_ids_probs = [(src_id,prob)]
                else:
                    raise SimulationError(f"Probability Calculation Error: Unrecognized OP Node! Node Name = {name}",1)

                for src_id,src_prob in src_node_ids_probs:
                    src_fault_list = self.circuit_graph_node[src_id].fault_list
                    for key in src_fault_list:
                        if (key in n_fault_list) and src_fault_list[key]["prob"] * src_prob < n_fault_list[key]["prob"]:
                            continue
                        n_fault_list[key] = {"prob":src_fault_list[key]["prob"] * src_prob, "type": src_fault_list[key]["type"]}
            self.circuit_graph_node[node_id].set_fault_list(n_fault_list)


    def simulate(self):
        print("=======================================")
        print(" Start Simulating Fault Propagation...")
        # Simulation Loop
        op_set = set()
        scheduled_node_num_list = self.scheduled_node_num_list[1:]
        cnt = 0
        cur_cyc_fault_list = {}
        #for node in self.circuit_graph_node:
        #    print(node,node.node_type)

        # Simulate by RTL Circuit Graph Propagation
        for node_id in scheduled_node_num_list:
            cnt +=1
            if self.circuit_graph_node[node_id].node_type in {"FF_out","input"}:
                # Check FF_out
                if self.circuit_graph_node[node_id].ready_flag:
                    pass
                else:
                    raise SimulationError("Warning: input FF not be set",1)
            elif self.circuit_graph_node[node_id].node_type == "OP":
                self._compute(node_id)
                #self._op_fault_propagate(node_id)
                self._op_prob_fault_propagate(node_id)
            else:
                self._assign(node_id)
                self._sig_fault_propagate(node_id)

            if self.circuit_graph_node[node_id].node_type == "FF_in":
                write_flag = False
                for src_reg in self.circuit_graph_node[node_id].fault_list:
                    if self.circuit_graph_node[node_id].fault_list[src_reg]["type"] == "data":
                        write_flag = True
                if not write_flag:
                    dst_reg = self.circuit_graph_node[node_id].name.replace("(FF_in)","")
                    self.circuit_graph_node[node_id].fault_list[dst_reg] = {"prob":1.0,"type":"stay"}
                
                cur_cyc_fault_list[self.circuit_graph_node[node_id].name] = self.circuit_graph_node[node_id].fault_list
        
        # Observation of Propagation Result
        fault_effect_dict = {}
        for dst_reg in cur_cyc_fault_list.keys():
            for src_reg in cur_cyc_fault_list[dst_reg]:
                prob = cur_cyc_fault_list[dst_reg][src_reg]["prob"]
                fault_type = cur_cyc_fault_list[dst_reg][src_reg]["type"]
                if not src_reg in fault_effect_dict:
                    fault_effect_dict[src_reg] = [(dst_reg.replace("(FF_in)",""),{"prob":prob,"type":fault_type})]
                else:
                    fault_effect_dict[src_reg].append((dst_reg.replace("(FF_in)",""),{"prob":prob,"type":fault_type}))
        cur_cyc_rw_events = []
        for (key, item) in fault_effect_dict.items():
            if key == "const" or key == "input":
                continue
            w_event = []
            stay_event = []
            ctrl_event = []
            for fault_effect in item:
                if fault_effect[1]["type"] == "data":
                    w_event.append((fault_effect[0],fault_effect[1]["prob"]))
                elif fault_effect[1]["type"] == "ctrl":
                    ctrl_event.append((fault_effect[0],fault_effect[1]["prob"]))
                else:
                    stay_event.append((fault_effect[0],fault_effect[1]["prob"]))
            cur_cyc_rw_events.append({"r":key, "w":w_event, "stay":stay_event, "ctrl":ctrl_event})

        print(" Simulation Finish.")
        print("=======================================")
        return cur_cyc_rw_events

    def seq_simulate(self):
        self.rw_table_cycle_col = []
        self.rw_table_event_col = []

        for cyc in range(1037):
            self.cycle = cyc
            self._load_logic_value()
            self.rw_table_event_col.append(self.simulate())
            self.rw_table_cycle_col.append(cyc)

    def dump_rw_table(self):
        df = pd.DataFrame({"cycle":self.rw_table_cycle_col, "rw_event":self.rw_table_event_col})
        df.to_csv("prob_rw_table.csv")

    def single_cycle_simulate(self,cyc:int):
        self.cycle = cyc
        self._load_logic_value()
        self.simulate()

if __name__ == "__main__":

    sim = RTL_Simulator()
    sim.seq_simulate()
    sim.dump_rw_table()
