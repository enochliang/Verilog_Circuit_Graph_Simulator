from AST_Analyzer import *

class AST_Checker(AST_Analyzer):
    def __init__(self, ast: etree._ElementTree):
        AST_Analyzer.__init__(self,ast)

    def get_info(self):
        pprint.pp(self.__dir__())

    def _get_loc_info(self,node):
        if "loc" in node.attrib:
            loc = node.attrib["loc"]
            _file = loc.split(",")[0]
            _file = self.ast.find(f".//file[@id='{_file}']").attrib["filename"]
            n_line = loc.split(",")[1]
            print(f"    File = {_file}, at line {n_line}.")

    def check_dtype(self,output=True) -> set:
        # Make a List of Packed dtype That Doesn't Start With Zero Bit.
        dtypes = set()
        for dtype in self.ast.findall(".//basicdtype"):
            if "right" in dtype.attrib:
                if not dtype.attrib["right"] == "0":
                    dtypes.add((("id",dtype.attrib["id"]),("left",dtype.attrib["left"]),("right",dtype.attrib["right"])))
        if output:
            print("Print Packed dtype That Doesn't Start With Zero Bit.")
            for dtype in dtypes:
                print(dtype)
        return dtypes

    def check_tag_all_x_are_under_y(self,x:str,y:str):
        target_nodes = self.ast.findall(".//"+x)
        flag = False
        for x_node in target_nodes:
            if not y in self.ast.getpath(x_node):
                print("Found a <"+x+"> not under <"+y+">")
                flag = True
        if not flag:
            print("ALL <"+x+"> are under <"+y+">")


    def _check_sel_no_muxdec(self):
        print("Start Checking No MUX or DEC in <sel>...")
        flag = False
        for sel in self.ast.findall(".//sel"):
            # Check if there is a variable in the bit selection braket.
            if not [c.tag for c in sel.getchildren()][1:] == ["const","const"]:
                print("  Warning: Found a <sel> with MUX or DEC!")
                self._get_loc_info(sel)
                sel_ctrl_signal = sel.getchildren()[1].find(".//varref").attrib["name"]
                print(f"    The variable in side bit selection braket = {sel_ctrl_signal}")
                flag = True
        if not flag:
            print("Pass: No MUX or DEC in <sel>")
        print("-"*80)



    def _check_lv_single_var(self):
        """Check all left value of assignment. 
        All of them should be a single <varref> on the left."""
        print("Start Checking Left Side of Assignment is A Single <varref>...")
        assignments = self.ast.findall(".//assign") + self.ast.findall(".//assigndly") + self.ast.findall(".//contassign")
        flag = False
        for assign in assignments:
            lv = assign.getchildren()[1]
            tag = lv.tag
            if not tag == "varref":
                print("  Warning: Found a Left Value Not a Single <varref>!")
                print("    Tag = "+tag)
                self._get_loc_info(lv)
                if tag == "sel":
                    print(f'    var = {assign.getchildren()[1].getchildren()[0].attrib["name"]}')
                flag = True
        if not flag:
            print("Pass: All Left Values are Single <varref>")
        print("-"*80)


    def _check_no_array(self):
        print("Start Checking No Array in The Design...")
        if not self.ast.find(".//arraysel") == None:
            print("  Warning: Found <arraysel>.")
            array_name = self.ast.find(".//arraysel").getchildren()[0].attrib["name"]
            print(f"  Array Name = {array_name}")
        else:
            print("Pass: No Array in Design.")
        print("-"*80)


    def _check_lv_only_left(self):
        print("Start Checking No Sequantial-Assignments Always-Block \n(All Left-Value Signals Should Be On the Left of Assignment in An Always-Block)...")
        for assign in self.ast.findall(".//always//assign") + self.ast.findall(".//always//assigndly"):
            assign.getchildren()[1].attrib["LV"] = "true"
        flag = False
        for always in self.ast.findall(".//always"):
            lv_set = set()
            for assign in always.findall(".//assign") + always.findall(".//assigndly"):
                lv_set.add(assign.getchildren()[1].attrib["name"])

            for node in always.iter():
                if(node.tag == "varref" and node.attrib["name"] in lv_set):
                    if("LV" in node.attrib):
                        pass
                    else:
                        print("  Warning: Found Left Value on the Right Side of Assignment.")
                        print("    Variable Name = "+node.attrib["name"])
                        flag = True
        if not flag:
            print("Pass: Left-Values Only on the Left of Assignment.")
        print("-"*80)


    def _check_ff_always_only_one_lv(self):
        print("Start checking each sequential <always> only has 1 Left-Value...")
        flag = False
        for always in self.ast.findall(".//always"):
            if always.find(".//sentree") == None:
                continue

            lv_set = set()
            for assign in always.findall(".//assign") + always.findall(".//assigndly"):
                for lv_var in assign.getchildren()[1].findall(".//varref"):
                    name = lv_var.attrib["name"]
                    lv_set.add(name)

            if len(lv_set) > 1:
                print("  Warning: More than 1 Left-Value in the <always>")
                print("    LVs in this <always> = ")
                pprint.pp(lv_set)
                flag = True

        if not flag:
            print("Pass: Each FF <always> only has 1 Left-Value")
        print("-"*80)

    def _check_comb_always_only_one_lv(self):
        print("Start checking each combinational <always> only has 1 Left-Value...")
        flag = False
        for always in self.ast.findall(".//always"):
            if always.find(".//sentree") != None:
                continue

            lv_set = set()
            for assign in always.findall(".//assign") + always.findall(".//assigndly"):
                for lv_var in assign.getchildren()[1].findall(".//varref"):
                    name = lv_var.attrib["name"]
                    lv_set.add(name)

            if len(lv_set) > 1:
                print("  Warning: More than 1 Left-Value in the <always>")
                print("    LVs in this <always> = ")
                pprint.pp(lv_set)
                flag = True

        if not flag:
            print("Pass: Each Comb <always> only has 1 Left-Value")
        print("-"*80)


    def _check_ff_always_fullcase(self):
        print("Start checking each sequential <always> is FULLCASE...")
        flag = False
        for always in self.ast.findall(".//always"):
            if always.find(".//sentree") == None:
                continue
            child = [i.tag for i in always.getchildren()]
            if "if" in child or "case" in child:
                if "assign" in child:
                    print("  Warning: Always not fullcase")
                    self._get_loc_info(always.find("assign"))
                    flag = True
        if not flag:
            print("Pass: Each FF <always> is FULLCASE")
        print("-"*80)

    def _check_comb_always_no_seq_assign(self):
        print("Start checking no sequential assignments under each combinational <always>...")
        flag = False
        for always in self.ast.findall(".//always"):
            if always.find(".//sentree") != None:
                continue

            child = [i.tag for i in always.getchildren()]
            if "if" in child or "case" in child:
                if "assign" in child:
                    print("  Warning: Found Sequential Assignments.")
                    loc = always.find("assign").attrib["loc"]
                    file_id = loc.split(",")[0]
                    loc = ",".join(loc.split(",")[1:])
                    print("    Assignment: "+self.ast.find(".//files//file[@id='"+file_id+"']").attrib["filename"]+","+loc)
                    flag = True

            for block in always.findall(".//begin") + always.findall(".//caseitem"):
                if len(block.findall("./if") + block.findall("./case")) > 1:
                    print("  Warning: Found Multiple <if> or <case> under <begin>")
                    print(f"    Always Block: {always.attrib}")
                    flag = True

        if not flag:
            print("Pass: Each Comb <always> is FULLCASE")
        print("-"*80)
    def _check_comb_always_fullcase(self):
        # TODO
        print("Start checking each combinational <always> is FULLCASE...")
        for always in self.ast.findall(".//always"):
            if always.find(".//sentree") != None:
                continue

            for branch in always.findall(".//if") + always.findall(".//case"):
                if branch.tag == "if":
                    if len(branch.getchildren()) < 3:
                        print("    Branch Tag = <if>")
                        self._get_loc_info(branch)
                        
                        #raise RTL_Coding_Style_Warning("Found a <if> without <else> case item.",1)

                if branch.tag == "case":
                    last_item = branch.getchildren()[-1]
                    ctrl_dtype = branch.getchildren()[0].attrib["dtype_id"]
                    dtype = self.ast.find(f".//basicdtype[@id='{ctrl_dtype}']")
                    if "left" in dtype.attrib:
                        width = int(dtype.attrib["left"]) - int(dtype.attrib["right"]) + 1
                        fullcase_num = pow(2,width)
                    else:
                        fullcase_num = 2

                    
                    if len(last_item.getchildren()) != 1: # The <case> doesn't have a <default> under it.
                        if len(branch.findall("./caseitem/const")) < fullcase_num: # The <case> has less than fullcase_num of <caseitem> under it.
                            print("    Branch Tag = <case>")
                            self._get_loc_info(branch)
                            #raise RTL_Coding_Style_Warning("Found a <case> without <default> case item, and not full case.",1)
                        
        print("Pass: Each Comb <always> is FULLCASE")
        print("-"*80)

    def _check_no_param_under_assign(self):
        print("Start checking no parameter under assignments...")
        flag = False
        for assign in self.ast.findall(".//contassign") + self.ast.findall(".//assignalias") + self.ast.findall(".//always//assign") + self.ast.findall(".//always//assigndly"):
            for var in assign.findall(".//varref"):
                if "param" in var.attrib or "localparam" in var.attrib:
                    print("Warning: Found Parameter under assignment!")
                    print("  parameter = "+var.attrib["name"])
                    flag = True

        if not flag:
            print("Pass: No parameter under assignments")
        print("-"*80)


    def _check_non_blocking_always_assignment(self):
        print("Start checking each non-blocking <always> only has <assigndly> in it...")
        flag = False
        for sentree in self.ast.findall(".//always/sentree"):
            nonblk_always = sentree.getparent()
            assign = nonblk_always.find(".//assign")
            if assign != None:
                print("  Warning: Found a <assign> in Non-blocking <always>.")
                flag = True
        if not flag:
            print("Pass: All Assignment in non-blocking <always> is <assigndly>")
        print("-"*80)


    def check_simple_design(self):
        print("#########################################")
        print("#    Start Checking Simple Design ...   #")
        print("#########################################")
        self._check_no_array()
        self._check_sel_no_muxdec()
        self._check_lv_single_var()
        #self._check_lv_only_left()
        self._check_comb_always_only_one_lv()
        self._check_comb_always_no_seq_assign()
        self._check_comb_always_fullcase()
        self._check_ff_always_only_one_lv()
        self._check_ff_always_fullcase()
        self._check_non_blocking_always_assignment()
        self._check_no_param_under_assign()
        self._check_param_not_in_circuit()
        #self._check_always_only_one_assign()

    def _check_always_only_one_assign(self):
        flag = False
        for always in self.ast.findall(".//always"):
            assign_num = len(always.findall(".//assign"))
            assigndly_num = len(always.findall(".//assigndly"))

            if assigndly_num + assign_num > 1:
                print("  Error: Found Multiple Assignment in <always>")
                if assigndly_num > 1:
                    lv_name = always.find(".//assigndly").getchildren()[1].attrib["name"]
                    print("    Error: Found Multiple <assigndly> in <always>")
                if assign_num > 1:
                    lv_name = always.find(".//assign").getchildren()[1].attrib["name"]
                    print("    Error: Found Multiple <assign> in <always>")
                flag = True

                print("    LV = "+lv_name)
        if not flag:
            print("Pass: Only 1 assignment in Each <always>.")
        print("-"*80)

    def _check_param_not_in_circuit(self):
        print("Start Checking Parameter are all replaced by <const>.")
        flag = False
        for var in self.ast.findall(".//var[@param='true']") + self.ast.findall(".//var[@localparam='true']"):
            var_name = var.attrib["name"]
            if self.ast.find(f".//varref[@name='{var_name}']") != None:
                flag = True
                print("    Warning: Found a parameter in <varref>.")
        if not flag:
            print("Pass: No Parameter in the Circuit.")
        print("-"*80)

if __name__ == "__main__":
    ast_file = "./ast/Vpicorv32_axi.xml"
    ast = Verilator_AST_Tree(ast_file)
    print("#"*len("# Start parsing ["+ast_file+"] #"))
    print("# Start parsing ["+ast_file+"] #")
    print("#"*len("# Start parsing ["+ast_file+"] #"))
    checker = AST_Checker(ast)
    checker.check_simple_design()
    #checker.get_info()


