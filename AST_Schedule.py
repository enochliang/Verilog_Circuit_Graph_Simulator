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

    def preprocess(self):
        self.split_register()
        self.numbering_subcircuit()
        self.numbering_assignment()

    def split_register(self):
        pass

    def numbering_assignment(self):
        assignment_id = 0
        for assign in self._ast.findall(".//contassign") + self._ast.findall(".//always//assign") + self._ast.findall(".//always//assigndly"):
            assign.attrib["assignment_id"] = str(assignment_id)
            assignment_id += 1

    def numbering_subcircuit(self):
        subcircuit_id = 0
        for sub_circuit in self._ast.findall(".//contassign") + self._ast.findall(".//always"):
            sub_circuit.attrib["subcircuit_id"] = str(subcircuit_id)
            subcircuit_id += 1




    def schedule_ast(self):
        self._ast_schedule = deepcopy(self._ast)
        self.schedule_subcircuit()

    def schedule_subcircuit(self):

    pass
