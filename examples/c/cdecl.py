""" Implement alike logic as is done on www.cdecl.org """
import argparse
import io
from ppci.api import get_current_platform
from ppci.lang.c import CLexer, CParser, COptions, CContext, CSemantics
from ppci.lang.c import types, declarations
from ppci.lang.c.preprocessor import prepare_for_parsing

parser = argparse.ArgumentParser()
parser.add_argument('source', type=str)
args = parser.parse_args()
# print('Source:', args.source)

# Parse into ast:
arch = get_current_platform()
coptions = COptions()
ccontext = CContext(coptions, arch.info)
semantics = CSemantics(ccontext)
cparser = CParser(ccontext, semantics)
clexer = CLexer(COptions())
f = io.StringIO(args.source)
tokens = clexer.lex(f, '<snippet>')
tokens = prepare_for_parsing(tokens, cparser.keywords)
cparser.init_lexer(tokens)
semantics.begin()
decl = cparser.parse_declarations()[0]

# Explain:
def explain(x):
    if isinstance(x, declarations.VariableDeclaration):
        return '{} is {}'.format(x.name, explain(x.typ))
    elif isinstance(x, types.PointerType):
        return 'a pointer to {}'.format(explain(x.element_type))
    elif isinstance(x, types.ArrayType):
        return 'an array of {}'.format(explain(x.element_type))
    elif isinstance(x, types.BareType):
        return '{}'.format(x.type_id)
    else:
        print('???', x)

print(explain(decl))
