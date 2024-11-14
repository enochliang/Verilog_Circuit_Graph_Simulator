from lxml import etree

class AST_2Verilog:
    def __init__(self, ast: etree._ElementTree):
        self.ast = ast
        pass
    def ast_construct(self):
        for self.ast.find(".//netlist").iter():

if __name__ == "__main__":
    ast_file = "./ast/Vpicorv32_axi.xml"
    ast = Verilator_AST_Tree(ast_file)
    converter = AST_2Verilog()
