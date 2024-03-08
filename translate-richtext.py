#!/usr/bin/env python3

# TODO export_lang must decode html entities to utf8
# TODO import_lang must encode html entities from utf8

# fixed: leading and trailing whitespace is lost when it should be part of text nodes
# this gives a different result than translate-richtext.js
# https://github.com/tree-sitter/tree-sitter-html/issues/87
# fixed in
# https://github.com/tree-sitter/tree-sitter-html/pull/89

import os
import sys
#import fs
import re
import glob
import io
#import path
import json
import shutil
import hashlib
import subprocess
import html
import urllib.parse
import ast

import tree_sitter_languages

tree_sitter_html = tree_sitter_languages.get_parser("html")

"""
text = b"<b>asdf</b>"
tree = tree_sitter_html.parse(text)
print(tree.root_node.sexp())
sys.exit()
"""

#from format_error_context import formatErrorContext

show_debug = False
#show_debug = True

# limit of google, deepl
char_limit = 5000

translator_name = 'google'

preview_text_length = 500

debug_alignment = False

translate_comments = False
translate_title_attr = False
translate_meta_content = True

remove_regex_char_class = ''.join([
    # ZERO WIDTH SPACE from google
    # https://stackoverflow.com/questions/36744793
    '\u200B',
])

artifacts_regex_char_class = ''.join([
    remove_regex_char_class,
    # space
    ' ',
])

code_num_regex_char_class = "0-9"

# "import" because this is used only in importLang
# where we have to deal with errors introduced by the translate service
code_num_regex_char_class_import = (
    code_num_regex_char_class +
    artifacts_regex_char_class
)


# https://stackoverflow.com/a/20372465/10440128
from inspect import currentframe
def __line__():
    cf = currentframe()
    return cf.f_back.f_lineno


def encode_num(num):
    return "ref" + str(num)



def sha1sum(_bytes):
    return hashlib.sha1(_bytes).hexdigest()


# NOTE xml processing instruction in xhtml gives a parse error
# <?xml version="1.0" encoding="UTF-8"?>
# https://github.com/tree-sitter/tree-sitter-html/issues/82
# but works with lezer-parser-html


# https://github.com/grantjenks/py-tree-sitter-languages/issues/59
# TODO better? get name-id mappings from parser binary?

# with open(os.environ["TREE_SITTER_HTML_SRC"] + "/src/grammar.json", "r") as f:
#     tree_sitter_html_grammar = json.load(f)
# # no. names can be ugly names like '"'
# # import types
# # node_kind = types.SimpleNamespace(**{
# #     name: id for id, name in enumerate(tree_sitter_html_grammar["rules"])
# # })
# node_kind = {
#     name: id for id, name in enumerate(tree_sitter_html_grammar["rules"])
# }
# print("node_kind =", json.dumps(node_kind, indent=2))

# parse node name-id mapping from src/parser.c

with open(os.environ["TREE_SITTER_HTML_SRC"] + "/src/parser.c", "rb") as f:
    parser_c_src = f.read()
tree_sitter_c = tree_sitter_languages.get_parser("c")
parser_c_tree = tree_sitter_c.parse(parser_c_src)

def walk_tree(tree):
    cursor = tree.walk()
    reached_root = False
    while reached_root == False:
        yield cursor.node
        if cursor.goto_first_child():
            continue
        if cursor.goto_next_sibling():
            continue
        retracing = True
        while retracing:
            if not cursor.goto_parent():
                retracing = False
                reached_root = True
            if cursor.goto_next_sibling():
                retracing = False

if False:

    # debug: print AST

    node_idx = 0
    max_len = 30

    for node in walk_tree(parser_c_tree.root_node):

        node_text = json.dumps(node_source)
        if len(node_text) > max_len:
            node_text = node_text[0:max_len] + "..."

        #pfx = "# " if is_compound else "  "
        pfx = ""
        print(pfx + f"node {node.kind_id:2d} = {node.type:25s} : {node_text:30s}")

        node_idx += 1
        #if node_idx > 100: break

    sys.exit()

in_enum_ts_symbol_identifiers = False
in_char_ts_symbol_names = False
enum_name = None
current_identifier = None
enum_ts_symbol_identifiers = dict()
char_ts_symbol_names = dict()

for node in walk_tree(parser_c_tree.root_node):

    node_source = node.text.decode("utf8")

    if node.type == "type_identifier" and node.text == b"ts_symbol_identifiers":
        in_enum_ts_symbol_identifiers = True
        continue

    if node.type == "pointer_declarator" and node.text == b"* const ts_symbol_names[]":
        in_char_ts_symbol_names = True
        continue

    if in_enum_ts_symbol_identifiers:

        if node.type == "identifier":
            current_identifier = node_source
            continue

        if node.type == "number_literal":
            enum_ts_symbol_identifiers[current_identifier] = (
                int(node_source)
            )
            current_identifier = None
            continue

        if node.type == "}":
            current_identifier = node_source
            in_enum_ts_symbol_identifiers = False
            continue

        continue

    if in_char_ts_symbol_names:

        if node.type == "subscript_designator":
            current_identifier = node_source[1:-1]
            continue

        if node.type == "string_literal":
            char_ts_symbol_names[current_identifier] = (
                ast.literal_eval(node_source)
            )
            current_identifier = None
            continue

        if node.type == "}":
            current_identifier = node_source
            in_char_ts_symbol_names = False
            break

        continue

#print("enum_ts_symbol_identifiers =", json.dumps(enum_ts_symbol_identifiers, indent=2))
#print("char_ts_symbol_names =", json.dumps(char_ts_symbol_names, indent=2))

# force user to use exact names from full_node_kind
# names can collide when grammars
# use the same names for different tokens...
# example: <!doctype html>
# both the full tag and the tag_name have the token name "doctype"
#   sym_doctype = 26, // full doctype tag
#   sym__doctype = 4, // tag_name of doctype tag

full_node_kind = enum_ts_symbol_identifiers
node_kind = dict()
for full_name, id in enum_ts_symbol_identifiers.items():
    name = char_ts_symbol_names[full_name]
    if len(list(filter(lambda n: n == name, char_ts_symbol_names.values()))) > 1:
        # duplicate name
        # force user to use full_name in full_node_kind
        # also store full_name in node_kind
        node_kind[full_name] = id
        continue
    node_kind[name] = id
# allow reverse lookup from id to name
node_name = [None] + list(node_kind.keys())

if show_debug:
    #print("full_node_kind =", json.dumps(full_node_kind, indent=2))
    print("node_kind =", json.dumps(node_kind, indent=2))
    #print("node_kind document =", node_kind["document"])

# compound tags
# these are ignored when serializing the tree
compound_kind_id = set([
    node_kind["document"],
    #node_kind["doctype"],
    full_node_kind["sym_doctype"], # full doctype tag
    #full_node_kind["sym__doctype"], # tag_name of doctype tag
    #node_kind["<!"],
    #node_kind[">"],
    node_kind["element"],
    node_kind["script_element"],
    node_kind["style_element"],
    node_kind["sym_start_tag"],
    node_kind["self_closing_tag"],
    node_kind["end_tag"],
    node_kind["attribute"],
    #node_kind["quoted_attribute_value"], # keyerror
    node_kind['"'], # double quote
    node_kind["'"], # single quote
    #node_kind["attribute_value"],
])

# https://github.com/tree-sitter/py-tree-sitter/issues/33
#def traverse_tree(tree: Tree):
#def walk_html_tree(tree, func, filter_compound_nodes=True):
def walk_html_tree(tree, keep_compound_nodes=False):
    global compound_kind_id
    cursor = tree.walk()
    reached_root = False
    while reached_root == False:
        is_compound = cursor.node.kind_id in compound_kind_id
        # if filter_compound_nodes:
        #     if not is_compound:
        #         yield cursor.node
        #         #func(cursor.node) # slow?
        # else:
        #     # dont filter
        #     #yield cursor.node
        #     func(cursor.node, is_compound)
        #if not is_compound:
        if keep_compound_nodes or not is_compound:
            yield cursor.node
            #func(cursor.node) # slow?
        if cursor.goto_first_child():
            continue
        if cursor.goto_next_sibling():
            continue
        retracing = True
        while retracing:
            if not cursor.goto_parent():
                retracing = False
                reached_root = True
            if cursor.goto_next_sibling():
                retracing = False



async def export_lang(input_path, target_lang, output_dir=""):
    # tree-sitter expects binary string
    #with open(input_path, 'r') as f:
    with open(input_path, 'rb') as f:
        input_html_bytes = f.read()

    input_html_hash = 'sha1-' + hashlib.sha1(input_html_bytes).hexdigest()
    input_path_frozen = output_dir + input_path + '.' + input_html_hash
    print(f'writing {input_path_frozen}')
    with open(input_path_frozen, 'wb') as f:
        f.write(input_html_bytes)

    translations_database_html_path_glob = output_dir + 'translations-google-database-*-*.html'
    translations_database = {}

    # parse translation databases
    print("parsing translation databases")
    for translations_database_html_path in glob.glob(translations_database_html_path_glob):
        print(f'reading {translations_database_html_path}')
        with open(translations_database_html_path, 'r') as f:
            parse_translations_database(translations_database, f.read())

    #html_parser = lezer_parser_html.configure()
    html_parser = tree_sitter_html

    # parse input html
    print("parsing input html")
    try:
        html_tree = html_parser.parse(input_html_bytes)
    except exception as error:
        if str(error).startswith("No parse at "):
            pos = int(str(error)[len("No parse at "):])
            error_message = str(error) + '\n\n' + format_error_context(input_html_bytes, pos)
            raise exception(error_message)
        raise error

    #root_node = html_tree.top_node # lezer-parser
    root_node = html_tree.root_node



    # debug: print the AST
    debug_print_ast = False
    #debug_print_ast = True

    if debug_print_ast:

        print("debug_print_ast")

        last_node_to = 0
        node_idx = -1

        max_len = 30

        for node in walk_html_tree(root_node, keep_compound_nodes=True):

            is_compound = node.kind_id in compound_kind_id

            node_text = json.dumps(node_source)
            if len(node_text) > max_len:
                node_text = node_text[0:max_len] + "..."

            space_node_text = json.dumps(input_html_bytes[last_node_to:node.range.end_byte].decode("utf8"))
            if len(space_node_text) > max_len:
                space_node_text = space_node_text[0:max_len] + "..."
            pfx = "# " if is_compound else "  "
            print(pfx + f"node {node.kind_id:2d} = {node.type:25s} : {node_text:30s} : {space_node_text}")
            last_node_to = node.range.end_byte

            node_idx += 1
            #if node_idx > 20: raise 123

        return


    check_parser_lossless = False
    #check_parser_lossless = True

    if check_parser_lossless:

        # test the tree walker
        # this test run should return
        # the exact same string as the input string
        # = lossless noop

        print("testing walk_html_tree")


        # https://github.com/tree-sitter/py-tree-sitter/issues/202
        # py-tree-sitter is 10x slower than lezer-parser
        #walk_html_tree_test_result = b"" # slow!

        walk_html_tree_test_result = io.BytesIO()

        last_node_to = 0

        node_idx = -1

        for node in walk_html_tree(root_node):

            # if is_compound:
            #     return
            # node_source_bytes = input_html_bytes[last_node_to:node.range.end_byte]
            # last_node_to = node.range.end_byte
            # walk_html_tree_test_result += node_source_bytes
            # return

            # debug...

            # if not input_html_bytes.startswith(walk_html_tree_test_result):
            #     print("is ok", False)
            #     print("writing walk_html_tree_test_result.html")
            #     with open("walk_html_tree_test_result.html", "wb") as f:
            #         f.write(walk_html_tree_test_result)
            #     raise 1234

            node_source_bytes = input_html_bytes[last_node_to:node.range.end_byte]
            last_node_to = node.range.end_byte
            #walk_html_tree_test_result += node_source_bytes # slow!
            walk_html_tree_test_result.write(node_source_bytes)

            # s = repr(node_source)
            # if len(s) > 50:
            #     s = s[0:50] + "..."
            # node_source = node_source_bytes.decode("utf8")
            # if len(node_source) > 50:
            #     node_source = node_source[0:50] + "..."
            # print(f"  node kind_id={node.kind_id:2d} type={node.type:10s} is_named={str(node.is_named):5s} {s:25s} {repr(node_source)}")

            node_idx += 1
            #if node_idx > 20: raise 123

        # copy whitespace after last node
        # fix: missing newline at end of file
        node_source_bytes = input_html_bytes[last_node_to:]
        #walk_html_tree_test_result += node_source_bytes # slow!
        walk_html_tree_test_result.write(node_source_bytes)

        walk_html_tree_test_result = walk_html_tree_test_result.getvalue()

        if walk_html_tree_test_result != input_html_bytes:
            print('error: the tree walker is not lossless')
            input_path_frozen_error = output_dir + input_path + '.' + input_html_hash + '.error'
            print(f'writing {input_path_frozen_error}')
            with open(input_path_frozen_error, 'w') as f:
                f.write(walk_html_tree_test_result)
            print(f'TODO: diff -u {input_path_frozen} {input_path_frozen_error}')
            print('TODO: fix the tree walker')
            sys.exit(1)

        print('ok. the tree walker is lossless')
        walk_html_tree_test_result = None

    class Tag:
        def __init__(self):
            self.open_space = None
            self.open = None
            self.name_space = None
            self.name = None
            self.attrs = []
            self.class_list = []
            self.parent = None
            self.lang = None
            self.ol = None # original language
            self.notranslate = False
            self.has_translation = False
            # FIXME these are never set?
            self._from = None
            self.to = None

    def new_tag():
        return Tag()

    last_node_to = 0
    in_notranslate_block = False
    current_tag = None
    attr_name = None
    attr_name_space = ""
    attr_is = None
    attr_is_space = ""
    attr_value_quote = None
    attr_value_quoted = None
    attr_value = None
    current_lang = None
    text_to_translate_list = []
    #output_template_html = "" # slow!
    output_template_html = io.StringIO()
    tag_path = []
    in_start_tag = False
    html_between_replacements_list = []
    last_replacement_end = 0
    in_doctype_node = False

    def is_self_closing_tag_name(tag_name):
        return tag_name in ('br', 'img', 'hr', 'meta', 'link', 'DOCTYPE', 'doctype')

    def is_sentence_tag(current_tag):
        if not current_tag:
            return False
        if show_debug:
            print("current_tag.name", repr(current_tag.name))
        return re.match(r"^(title|h[1-9]|div|li|td)$", current_tag.name) != None

    # function nodeSourceIsEndOfSentence
    def node_source_is_end_of_sentence(node_source):
        return re.search(r'[.!?]["]?\s*$', node_source) != None

    def should_translate_current_tag(current_tag, in_notranslate_block, current_lang, target_lang):
        return (
            not in_notranslate_block and
            not current_tag.notranslate and
            # TODO remove. moved to current_tag.notranslate
            #not current_tag.has_translation and
            current_tag.lang != target_lang
            # TODO remove. lang inheritance moved to new_tag()
            #current_lang != target_lang
        )

    def write_comment(*a):
        return
        s = " ".join(map(str, a))
        # TODO escape "-->" in s
        output_template_html.write(f"\n<!-- " + s + " -->\n")

    def format_tag(t):
        name = t.name or "(noname)"
        lang = t.lang or "?"
        translate = "N" if t.notranslate else "Y"
        return f"{name}.{lang}.{translate}"

    def format_tag_path(tag_path):
        return "".join(map(lambda t: "/" + format_tag(t), tag_path))
        #return "".join(map(lambda t: "/" + (t.name or "(noname)"), tag_path))

    # def walk_callback(node, is_compound):
    #     if is_compound:
    #         return
    #     # ...

    # def walk_callback_main
    #def walk_callback(node):
    #def walk_callback_main(node, is_compound):

    print("walk_html_tree")

    for node in walk_html_tree(root_node):

        # nonlocal last_node_to
        # nonlocal in_notranslate_block
        # nonlocal current_tag
        # nonlocal attr_name
        # nonlocal attr_name_space
        # nonlocal attr_is
        # nonlocal attr_is_space
        # nonlocal attr_value_quote
        # nonlocal attr_value_quoted
        # nonlocal attr_value
        # nonlocal current_lang
        # nonlocal text_to_translate_list
        # nonlocal output_template_html
        # nonlocal tag_path
        # nonlocal in_start_tag
        # nonlocal html_between_replacements_list
        # nonlocal last_replacement_end
        # nonlocal in_doctype_node

        # off by one error?
        # or how is ">" added?
        # node_source = input_html_bytes[last_node_to:node.range.end_byte].decode("utf8")
        # node_source_space_before = input_html_bytes[last_node_to:node.range.start_byte].decode("utf8")

        node_type_id = node.kind_id
        node_type_name = node.type

        #node_source = input_html_bytes[node.range.start_byte:node.range.end_byte].decode("utf8")
        node_source = node.text.decode("utf8")

        #node_source_space_before = input_html_bytes[(last_node_to + 1):node.range.start_byte].decode("utf8")
        node_source_space_before = input_html_bytes[(last_node_to):node.range.start_byte].decode("utf8")

        if show_debug:
            s = repr(node_source)
            if len(s) > 500:
                s = s[0:500] + "..."
            print(__line__(), "node", format_tag_path(tag_path), node.kind_id, node_name[node.kind_id], repr(node_source_space_before), repr(s))

        def write_node():
            # copy this node with no changes
            nonlocal last_node_to
            output_template_html.write(
                node_source_space_before + node_source
            )
            if show_debug:
                print("output_template_html.write", __line__(), repr(
                    node_source_space_before + node_source
                ))
            last_node_to = node.range.end_byte

        # fix: node_source_space_before == 'html'
        # workaround
        # doctype: parse all child nodes
        # https://github.com/tree-sitter/tree-sitter-html/issues/83
        # node 1 = <!: '<!' -> '<!'
        # node 4 = doctype: 'DOCTYPE' -> 'DOCTYPE'
        # node 3 = >: '>' -> '>'
        #if node_type_id == node_kind["<!"]:
        if node_type_id == node_kind["<!"] or node_type_id == node_kind["sym__doctype"]:
            in_doctype_node = True
            #last_node_to = node.range.end_byte
            write_node()
            continue

        elif node_type_id == node_kind[">"] and in_doctype_node == True:
            in_doctype_node = False
            #in_start_tag = False
            write_node()
            continue

            # in_start_tag = False
            # node_source = input_html_bytes[(last_node_to + 1):node.range.end_byte].decode("utf8")
            # node_source_space_before = ""
            # last_node_to = node.range.start_byte - 1
            # tag_path.pop()
            # try:
            #     current_tag = tag_path[-1]
            # except IndexError:
            #     current_tag = None
            # output_template_html.write(
            #     node_source_space_before + node_source
            # )
            # print("output_template_html.write", __line__(), repr(
            #     node_source_space_before + node_source
            # ))
            # # TODO?
            # last_node_to = node.range.end_byte
            # continue

        if show_debug:
            s2 = repr(node_source)
            if len(s2) > 500:
                s2 = s2[0:500] + "..."
            print(f"node {node.kind_id} = {node.type}: {s} -> {s2}")

        # validate node_source_space_before
        if re.match(r"""^\s*$""", node_source_space_before) == None:
            print("node_source_space_before", __line__(), repr(node_source_space_before))
            print((
                f'error: node_source_space_before must match the regex "\\s*". ' +
                'hint: add "last_node_to = node.range.end_byte;" before "return;"'
            ), {
                'lastNodeTo': last_node_to,
                'nodeFrom': node.range.start_byte,
                'nodeTo': node.range.end_byte,
                'nodeSourceSpaceBefore': node_source_space_before,
                'nodeSource': node_source,
                # FIXME this can break utf8
                'nodeSourceContext': input_html_bytes[node.range.start_byte - 100:node.range.end_byte + 100].decode("utf8"),
            })
            sys.exit(1)

        if node_source == '<!-- <notranslate> -->':
            in_notranslate_block  = True
            #output_template_html += (
            output_template_html.write(
                node_source_space_before + node_source
            )
            if show_debug:
                print("output_template_html.write", __line__(), repr(
                    node_source_space_before + node_source
                ))
            last_node_to = node.range.end_byte
            #return
            continue
        elif node_source == '<!-- </notranslate> -->':
            in_notranslate_block = False
            #output_template_html += (
            output_template_html.write(
                node_source_space_before + node_source
            )
            if show_debug:
                print("output_template_html.write", __line__(), repr(
                    node_source_space_before + node_source
                ))
            last_node_to = node.range.end_byte
            #return
            continue

        """
        node 5 < 1 '< ...'
        node 17 tag_name 4 'head ...'
        node 3 > 1 '> ...'

        node 7 </ 2 '</ ...'
        node 17 tag_name 5 'title ...'
        node 3 > 1 '> ...'
        """

        # start of open tag
        # if node_type_name == "StartTag":
        # node 1 '<!'
        # node 5 '<'
        if node_type_id == node_kind["<!"] or node_type_id == node_kind["<"]:
            parent_tag = current_tag
            # if True:
            #     write_comment(__line__(), f"current_tag = new_tag()")
            current_tag = new_tag()
            # if True:
            #     write_comment(__line__(), "current_tag =", repr(current_tag))
            # if True:
            #     write_comment(__line__(), "current_tag.attrs =", repr(list(map(lambda a: "".join(a), current_tag.attrs))))
            if parent_tag:
                # inherit notranslate from parent
                current_tag.notranslate = parent_tag.notranslate
                current_tag.lang = parent_tag.lang
                current_tag.parent = parent_tag
            # no. notranslate blocks are outside of the html node tree
            # if in_notranslate_block:
            #     current_tag.notranslate = True
            tag_path.append(current_tag)
            if show_debug:
            #if True:
                #write_comment(__line__(), f"tag_path += {current_tag.name} -> tag_path: " + format_tag_path(tag_path))
                print(__line__(), f"tag_path += {current_tag.name} -> tag_path: " + format_tag_path(tag_path))
            in_start_tag = True
            #print(__line__(), f"node {node_type_id} -> in_start_tag=True")
            current_tag.open_space = node_source_space_before
            current_tag.open = node_source
            # dont write. wait for end of start tag
            last_node_to = node.range.end_byte
            continue

        # start of close tag
        # "</"
        # elif node_type_name == "StartCloseTag":
        # TODO sym__start_tag_name
        elif node_type_id == node_kind["</"]: # node 7 </ 2 '</ ...'
            if show_debug:
                print(f"tag_path: " + format_tag_path(tag_path))
            if is_sentence_tag(current_tag):

                if current_lang is None:
                    source_start = node_source[:100]
                    # TODO show "outerHTML". this is only the text node
                    raise ValueError(f"node has no lang attribute: {repr(source_start)}")

                text_to_translate = [
                    len(text_to_translate_list),  # textIdx
                    "",  # nodeSourceTrimmedHash
                    current_lang,
                    ".",  # nodeSourceTrimmed
                    1,  # todoRemoveEndOfSentence
                    0,  # todoAddToTranslationsDatabase
                ]

                text_to_translate_list.append(text_to_translate)

                # htmlBetweenReplacementsList.push("");
                html_between_replacements_list.append("")
                if show_debug:
                    print("html_between_replacements_list[-1]", __line__(), repr(html_between_replacements_list[-1]))

        # end of tag
        # or
        # end of self-closing tag

        # lezer-parser-html
        # 36: node 4 = EndTag: 1: ">"
        # 23: node 4 = EndTag: 2: "/>"

        # lezer-parser-html with dialect = selfClosing
        # https://github.com/lezer-parser/html/issues/13
        # 36: node 4 = EndTag: 1: ">"
        # 23: node xxx = SelfClosingEndTag: 2: "/>"

        # tree-sitter-html
        # node 3 = >: ">"
        # node 6 = />: "/>"

        elif node_type_id == node_kind[">"] or node_type_id == node_kind["/>"]:

            if show_debug:
                print(f"node {node_type_id}: current_tag.name = {current_tag.name}")
                print(f"node {node_type_id}: in_start_tag = {in_start_tag}")
                print(f"node {node_type_id}: is_self_closing_tag = {is_self_closing_tag_name(current_tag.name)}")

            if in_start_tag:
                # end of start tag
                if show_debug:
                    print(f"node {node_type_id}: end of start tag -> in_start_tag=False")
                # process and write the start tag

                write_comment(json.dumps({
                    "tag_path": format_tag_path(tag_path),
                    "current_tag.name": current_tag.name,
                    "current_tag.notranslate": current_tag.notranslate,
                    "current_tag.attrs": list(map(lambda a: "".join(a), current_tag.attrs)),
                }, indent=2))

                # write " <some_name"
                output_template_html.write(
                    # " <"
                    current_tag.open_space + current_tag.open +
                    # "some_name"
                    current_tag.name_space + current_tag.name +
                    ""
                )

                #if current_tag.notranslate or current_tag.lang == target_lang:
                if not should_translate_current_tag(current_tag, in_notranslate_block, current_lang, target_lang):
                    # preserve attributes
                    for attr_item in current_tag.attrs:
                        output_template_html.write("".join(attr_item))

                #if should_translate_current_tag(current_tag, in_notranslate_block, current_lang, target_lang):
                else:
                    # modify attributes
                    for attr_item in current_tag.attrs:

                        (
                            attr_name_space,
                            attr_name,
                            attr_is_space,
                            attr_is,
                            attr_value_space,
                            attr_value_quote,
                            attr_value,
                            attr_value_quote,
                        ) = attr_item

                        # modify attribute
                        if attr_name == "lang":
                            attr_value = target_lang

                        # translate attribute value in some cases
                        # <meta name="description" content="...">
                        # <meta name="keywords" content="...">
                        # <div title="...">...</div>
                        # other <meta> tags are already guarded by <notranslate>
                        if (
                            (translate_title_attr and attr_name == "title")
                            or
                            (translate_meta_content and current_tag.name == 'meta' and attr_name == "content")
                        ):
                            # TODO later
                            # TODO export_lang must decode html entities to utf8
                            #attr_value_text = html.unescape(attr_value)
                            # TODO import_lang must encode html entities from utf8
                            #attr_value = html.escape(attr_value_text)

                            attr_value_hash = sha1sum(attr_value.encode("utf8"))
                            text_idx = len(text_to_translate_list)
                            node_source_key = f"{text_idx}_{current_lang}_{attr_value_hash}"
                            todo_remove_end_of_sentence = 0

                            if not node_source_is_end_of_sentence(attr_value):
                                attr_value += "."
                                todo_remove_end_of_sentence = 1

                            translation_key = f"{current_lang}:{target_lang}:{attr_value_hash}"

                            todo_add_to_translations_database = 0 if translation_key in translations_database else 1

                            if current_lang is None:
                                source_start = node_source[:100]
                                # TODO show "outerHTML". this is only the text node
                                raise ValueError(f"node has no lang attribute: {repr(source_start)}")

                            text_to_translate = [
                                text_idx,
                                attr_value_hash,
                                current_lang,
                                attr_value,
                                todo_remove_end_of_sentence,
                                todo_add_to_translations_database,
                            ]

                            text_to_translate_list.append(text_to_translate)

                            # store outputHtml between the last replacement and this replacment
                            output_template_html.seek(last_replacement_end)
                            html_between_replacements_list.append("".join((
                                output_template_html.read(),
                                attr_name_space,
                                attr_name,
                                attr_is_space,
                                attr_is,
                                attr_value_space,
                                attr_value_quote,
                                #attr_value,
                                #attr_value_quote,
                            )))

                            attr_value = f"{{TODO_translate_{node_source_key}}}"

                            # store end position of attr_value
                            last_replacement_end = output_template_html.tell() + len("".join((
                                attr_name_space,
                                attr_name,
                                attr_is_space,
                                attr_is,
                                attr_value_space,
                                attr_value_quote,
                                attr_value,
                                #attr_value_quote,
                            )))

                        # write attribute
                        attr_item = (
                            attr_name_space,
                            attr_name,
                            attr_is_space,
                            attr_is,
                            attr_value_space,
                            attr_value_quote,
                            attr_value,
                            attr_value_quote,
                        )
                        output_template_html.write("".join(attr_item))

                        if (
                            attr_name == "lang" and
                            current_tag.lang != target_lang and
                            current_tag.ol is None
                        ):
                            # add "ol" attribute after "lang" attribute
                            output_template_html.write(
                                f' ol="{current_tag.lang}"'
                            )

            if (
                # self-closing tag "<br>"
                (in_start_tag == True and is_self_closing_tag_name(current_tag.name)) or
                # close tag "</div>"
                in_start_tag == False
                #or
                #in_doctype_node == True
            ):
                # end of close tag
                if show_debug:
                    print(f"node {node_type_id}: end of close tag")
                closed_tag = tag_path.pop()
                if show_debug:
                    print(f"tag_path -= {closed_tag.name} -> tag_path: " + format_tag_path(tag_path))
                try:
                    current_tag = tag_path[-1]
                except IndexError:
                    current_tag = None
                current_lang = None
                for i in range(len(tag_path) - 1, -1, -1):
                    if tag_path[i].lang:
                        current_lang = tag_path[i].lang
                        break
                #in_start_tag = False

            #print(__line__(), f"node {node_type_id} -> in_start_tag=False")
            in_start_tag = False

        # TagName in StartTag
        # node 4 = doctype: 'DOCTYPE' # sym__doctype
        # node 17 = tag_name: "img" # sym__start_tag_name
        elif node_type_id == full_node_kind["sym__doctype"] or node_type_id == node_kind["sym__start_tag_name"]:
            if current_tag.name is None:
                current_tag.name_space = node_source_space_before
                current_tag.name = node_source
                if show_debug:
                    print(f"current_tag.name = {current_tag.name} -> tag_path: " + format_tag_path(tag_path))
            if in_start_tag:
                # dont write. wait for end of start tag
                last_node_to = node.range.end_byte
                continue

        # AttributeName in StartTag
        elif node_type_id == node_kind["attribute_name"]:
            attr_name = node_source
            attr_name_space = node_source_space_before
            # dont output the AttributeName node yet
            # wait for AttributeValue
            last_node_to = node.range.end_byte
            #return
            continue

        # Is ("=") in StartTag
        #elif in_start_tag and node_type_name == "Is":
        elif node_type_id == node_kind["="]:
            attr_is = node_source
            attr_is_space = node_source_space_before
            # dont output the Is node yet
            # wait for AttributeValue
            last_node_to = node.range.end_byte
            #return
            continue

        #14, # double quote '"'
        #12, # single quote "'"
        # elif node_type_id == 14 or node_type_id == 12:
        #     #attr_value_quote = node_source
        #     if attr_name:
        #         attr_value_quote = node_source
        #     last_node_to = node.range.end_byte
        #     continue

        # FIXME handle boolean attributes
        # <details open>
        # <option selected>

        # AttributeValue in StartTag
        # tree-sitter-html: attribute_value is without quotes
        # lezer-parser-html: attribute_value is with quotes
        # node 14 = ": "\""
        # node 10 = attribute_value: "asdf"
        # node 14 = ": "\""
        #elif node_type_id == 26:
        #elif node_type_id == 10:
        elif node_type_id in (
            node_kind["doublequoted_attribute_value"],
            node_kind["singlequoted_attribute_value"],
            node_kind["unquoted_attribute_value"],
        ):
            # lezer-parser-html
            # patched tree-sitter-html
            # https://github.com/tree-sitter/tree-sitter-html/pull/90

            attr_value_space = node_source_space_before

            if node_type_id == node_kind["unquoted_attribute_value"]:
                attr_value_quote = ""
                attr_value = node_source
                #attr_value_quoted = attr_value

            else:
                #quote = attr_value_quote
                #attr_value_quote = None
                attr_value_quote = node_source[0]
                #attr_value = node_source
                attr_value = node_source[1:-1]  # remove quotes
                #attr_value_quoted = quote + node_source + quote
                #attr_value_quoted = node_source

            # buffer all attributes, wait for end of start tag
            # class="notranslate" can come after lang="en"
            attr_item = (
                attr_name_space,
                attr_name,
                attr_is_space,
                attr_is,
                attr_value_space,
                attr_value_quote,
                attr_value,
                attr_value_quote,
            )
            #print(__line__(), "attr_item", "".join(attr_item))
            current_tag.attrs.append(attr_item)

            if attr_name == "lang":
                current_tag.lang = attr_value
                current_lang = attr_value
                # no. wrong!
                # TODO move
                # if current_tag.lang == target_lang:
                #     current_tag.notranslate = True

            # ol = original language
            elif attr_name == "ol":
                current_tag.ol = attr_value

            # ignore tags with attribute: class="notranslate"
            elif attr_name == "class":
                #class_list = set(attr_value.split())
                class_list = attr_value.split()
                current_tag.class_list += class_list
                if "notranslate" in class_list:
                    current_tag.notranslate = True

            # ignore tags with attribute: src-lang-id="..."
            elif attr_name == "src-lang-id":
                if attr_value.startswith(target_lang + ":"):
                    #current_tag.has_translation = True
                    current_tag.notranslate = True

            # ignore tags with attribute: style="display:none"
            # TODO also ignore all child nodes of such tags
            elif attr_name == "style":
                # TODO parse CSS. this can be something stupid like
                # style="/*display:none*/"
                if re.search(r"\b(display\s*:\s*none)\b", attr_value) != None:
                    current_tag.notranslate = True

            #print("attr_name", __line__(), repr(attr_name))

            attr_name = None

            # dont write. wait for end of start tag
            last_node_to = node.range.end_byte
            continue

        # end of: elif node_type_id == 10

        # TODO? filter EntityReference in AttributeValue
        # for now, this is only needed for lezer-parser-html
        # see also
        # https://github.com/tree-sitter/tree-sitter-html/issues/51
        # # if node_type_id == 17:  # EntityReference
        # if node_type_id == xxxxxx:  # EntityReference
        #     if in_attribute_value:
        #         # EntityReference is already in AttributeValue
        #         # so don't copy the EntityReference
        #         # but when in a text node
        #         # copy the EntityReference
        #         return

        # node 16 = text
        # if (nodeTypeId == 16) { // Text
        # no. never translate &some_entity; and <script> and <style>
        # TODO for the "joined" translation, decode entities to unicode chars
        # example: &mdash; -> \u2014 https://www.compart.com/en/unicode/U+2014
        # example: &amp; -> &
        # ... but we have to locate and revert these replacements via the "splitted" translation
        # nodeTypeId == 17 || // EntityReference // "&amp;" or "&mdash;" or ...
        # nodeTypeId == 28 || // ScriptText
        # nodeTypeId == 31 || // StyleText
        if node_type_id == node_kind["text"]:
            if (node_source_space_before + node_source).strip() == "":
                #output_template_html += (
                output_template_html.write(
                    node_source_space_before + node_source
                )
                if show_debug:
                    print("output_template_html.write", __line__(), repr(
                        node_source_space_before + node_source
                    ))
                last_node_to = node.range.end_byte
                continue
                return

            if should_translate_current_tag(current_tag, in_notranslate_block, current_lang, target_lang):
            #if current_tag.notranslate == False and current_tag.lang != target_lang:
                # TODO also compare source and target language
                # if they are equal, no need to translate
                # let nodeSourceTrimmed = nodeSource;
                #node_source_trimmed = node_source.strip()
                node_source_trimmed = node_source
                node_source_trimmed_hash = sha1sum(node_source_trimmed.encode("utf8"))
                text_idx = len(text_to_translate_list)
                node_source_key = f"{text_idx}_{current_lang}_{node_source_trimmed_hash}"
                todo_remove_end_of_sentence = 0

                # no. one node can have multiple text child nodes
                # example: Text EntityReference Text
                # fix: add "." only before StartCloseTag
                #if not node_source_is_end_of_sentence(node_source_trimmed) and is_sentence_tag(current_tag):
                #    node_source_trimmed += "."
                #    todo_remove_end_of_sentence = 1

                translation_key = f"{current_lang}:{target_lang}:{node_source_trimmed_hash}"
                todo_add_to_translations_database = 1 if translation_key not in translations_database else 0

                if current_lang is None:
                    source_start = node_source[:100]
                    # TODO show "outerHTML". this is only the text node
                    raise ValueError(f"node has no lang attribute: {repr(source_start)}")

                text_to_translate = [
                    text_idx,
                    node_source_trimmed_hash,
                    current_lang,
                    node_source_trimmed,
                    todo_remove_end_of_sentence,
                    todo_add_to_translations_database,
                ]

                text_to_translate_list.append(text_to_translate)

                output_template_html.seek(last_replacement_end)
                html_between_replacements_list.append(
                    #output_template_html[last_replacement_end:] + node_source_space_before
                    output_template_html.read() + node_source_space_before
                )
                if show_debug:
                    print("html_between_replacements_list[-1]", __line__(), repr(html_between_replacements_list[-1]))

                #output_template_html += (
                output_template_html.write(
                    node_source_space_before + "{TODO_translate_" + node_source_key + "}"
                )
                if show_debug:
                    print("output_template_html.write", __line__(), repr(
                        node_source_space_before + "{TODO_translate_" + node_source_key + "}"
                    ))
                last_replacement_end = output_template_html.tell()
                last_node_to = node.range.end_byte
                continue
                return

        # node 24 = comment
        # if (nodeTypeId == 39) { // Comment
        elif node_type_id == node_kind["comment"]:
            if (
                not translate_comments or
                not should_translate_current_tag(current_tag, in_notranslate_block, current_lang, target_lang)
            ):
                #output_template_html += (
                output_template_html.write(
                    node_source_space_before + node_source
                )
                if show_debug:
                    print("output_template_html.write", __line__(), repr(
                        node_source_space_before + node_source
                    ))
                last_node_to = node.range.end_byte
                continue
                return

            comment_content_with_prefix = node_source[4:-3]  # Removing "<!--" and "-->"
            comment_lang_match = re.match(r'\(lang="([a-z+]{2,100})"\)', comment_content_with_prefix)
            comment_lang = comment_lang_match.group(1) if comment_lang_match else None
            comment_lang_prefix = comment_lang_match.group(0) if comment_lang_match else ""
            comment_content = comment_content_with_prefix[len(comment_lang_prefix):]

            if (node_source_space_before + comment_content).strip() == "":
                #output_template_html += (
                output_template_html.write(
                    node_source_space_before + node_source
                )
                if show_debug:
                    print("output_template_html.write", __line__(), repr(
                        node_source_space_before + node_source
                    ))
                last_node_to = node.range.end_byte
                continue
                return

            if should_translate_current_tag(current_tag, in_notranslate_block, current_lang, target_lang):
                # TODO also compare source and target language
                # if they are equal, no need to translate
                # let nodeSourceTrimmed = commentContent;
                #node_source_trimmed = comment_content.strip()
                node_source_trimmed = comment_content
                node_source_trimmed_hash = sha1sum(node_source_trimmed.encode("utf8"))
                text_idx = len(text_to_translate_list)
                node_source_key = f"{text_idx}_{comment_lang or current_lang}_{node_source_trimmed_hash}"
                todo_remove_end_of_sentence = 0

                if (
                    not node_source_is_end_of_sentence(node_source_trimmed) and
                    is_sentence_tag(current_tag)
                ):
                    node_source_trimmed += "."
                    todo_remove_end_of_sentence = 1

                translation_key = f"{current_lang}:{target_lang}:{node_source_trimmed_hash}"
                todo_add_to_translations_database = 1 if translation_key not in translations_database else 0

                if current_lang is None:
                    source_start = node_source[:100]
                    # TODO show "outerHTML". this is only the text node
                    raise ValueError(f"node has no lang attribute: {repr(source_start)}")

                text_to_translate = [
                    text_idx,
                    node_source_trimmed_hash,
                    current_lang,
                    node_source_trimmed,
                    todo_remove_end_of_sentence,
                    todo_add_to_translations_database,
                ]

                text_to_translate_list.append(text_to_translate)

                # store outputHtml between the last replacement and this replacment
                output_template_html.seek(last_replacement_end)
                html_between_replacements_list.append(
                    #output_template_html[last_replacement_end:] + node_source_space_before
                    output_template_html.read() + node_source_space_before
                )
                if show_debug:
                    print("html_between_replacements_list[-1]", __line__(), repr(html_between_replacements_list[-1]))

                # TODO store context of replacement: attribute value with quotes (single or double quotes?)
                # then escape the quotes in the translated text
                #output_template_html += (
                output_template_html.write(
                    f"{node_source_space_before}<!--{{TODO_translate_{node_source_key}}}-->"
                )
                if show_debug:
                    print("output_template_html.write", __line__(), repr(
                        f"{node_source_space_before}<!--{{TODO_translate_{node_source_key}}}-->"
                    ))
                last_replacement_end = output_template_html.tell() - 3
                last_node_to = node.range.end_byte
                continue

        # default: copy this node
        if show_debug:
            print("node", __line__(), node.kind_id, node_name[node.kind_id], node)
        #output_template_html += (
        output_template_html.write(
            node_source_space_before + node_source
        )
        if show_debug:
            print("output_template_html.write", __line__(), repr(
                node_source_space_before + node_source
            ))
        last_node_to = node.range.end_byte
        continue
        return
    # def walk_callback_main end



    if current_tag != None:
        print((
            'error: end of the document ' +
            'reached with unclosed tags. ' +
            'hint: check if all the tags opened ' +
            'at line 1 were closed.'
        ))
        print("tag_path: " + format_tag_path(tag_path))
        sys.exit(1)

    # html after the last replacement
    output_template_html.seek(last_replacement_end)
    html_between_replacements_list.append(
        #output_template_html[last_replacement_end:]
        output_template_html.read()
    )
    if show_debug:
        print("html_between_replacements_list[-1]", __line__(), repr(html_between_replacements_list[-1]))

    # const outputTemplateHtmlPath = inputPath + '.' + inputHtmlHash + '.outputTemplate.html';
    output_template_html_path = output_dir + input_path + '.' + input_html_hash + '.outputTemplate.html'
    print(f"writing {output_template_html_path}")
    output_template_html = output_template_html.getvalue()
    with open(output_template_html_path, 'w') as f:
        f.write(output_template_html)

    text_to_translate_list_path = output_dir + input_path + '.' + input_html_hash + '.textToTranslateList.json'
    print(f"writing {text_to_translate_list_path}")
    with open(text_to_translate_list_path, 'w') as f:
        json.dump(text_to_translate_list, f, indent=2)

    html_between_replacements_path = output_dir + input_path + '.' + input_html_hash + '.htmlBetweenReplacementsList.json'
    print(f"writing {html_between_replacements_path}")
    with open(html_between_replacements_path, 'w') as f:
        json.dump(html_between_replacements_list, f, indent=2)

    # TODO build chunks of same language
    # limited by charLimit = 5000

    # new code -> old code
    # textToTranslateList -> textParts

    # const replacementData = {};
    replacement_data = {}
    replacement_data['replacementList'] = {}
    replacement_data['lastId'] = -1
    replacement_data_lastId_2 = -1



    # def fmt_num(num):
    #     # split long number in groups of three digits
    #     # https://stackoverflow.com/a/6786040/10440128
    #     # return `${num}`.replace(/(\d)(?=(\d{3})+$)/g, '$1 ');
    #     return '{:,}'.format(num)



    # wrong?
    # def get_replace(match):
    #     nonlocal replacement_data
    #     nonlocal replacement_data_lastId_2
    #     replacement_id = replacement_data_lastId_2 + 1
    #     code = encode_num(replacement_id)
    #     replacement_data['replacementList'][replacement_id] = {
    #         'value': match,
    #         'code': code,
    #         'indentList': []
    #     }
    #     replacement_data_lastId_2 += 1
    #     return f' [{code}] '



    def get_replace(match):
        nonlocal replacement_data
        replacement_id = replacement_data["lastId"] + 1
        replacement_data["lastId"] = replacement_id
        code = encode_num(replacement_id)
        replacement_data["replacementList"][replacement_id] = {
            "value": match,
            "code": code,
            "indentList": []
        }
        return f" [{code}] "



    # function stringifyRawTextGroup
    def stringify_raw_text_group(text_group_raw):
        """
        Constructs a string from a list of text groups, inserting placeholders for replacements.
        
        Parameters:
        - text_group_raw: A list of lists, where each inner list represents a part of the text. The first element
                        is the text or replacement, the second indicates if it's a replacement (0 for no, 1 for yes),
                        and the third (if present) is the replacement ID.
        
        Returns:
        - A string with the original text and placeholders for replacements.
        """
        result = []
        for part in text_group_raw:
            if part[1] == 0:
                # This part is not a replacement, so add its text directly.
                result.append(part[0])
            else:
                # This part is a replacement, so insert a placeholder with its ID.
                result.append(f" [ref{part[2]}] ")
        return "".join(result)



    # function stringifyDecodedDecodedRawTextGroup
    def stringify_decoded_decoded_raw_text_group(text_group_raw, html_between_replacements_list):
        """
        Decodes the replacement values in the text group and restores HTML content where applicable.
        
        Parameters:
        - text_group_raw: A list of lists, where each inner list represents a part of the text. The first element
                        is the text or replacement value, the second indicates if it's a replacement (0 for no, 1 for yes),
                        and the third (if present) is the replacement ID.
        - html_between_replacements_list: A list containing the HTML content before each replacement.
        
        Returns:
        - A string with the decoded text and restored HTML content.
        """
        result = []
        for part in text_group_raw:
            if part[1] == 0:
                # This part is not a replacement, so add its text directly.
                result.append(part[0])
            else:
                # This part is a replacement, so decode it if it represents HTML content.
                replacement_value = part[0]
                if replacement_value.startswith('<html '):
                    # Parse text part index from replacement_value
                    match = re.match(r'<html i="(\d+)" h="([^"]*)" rme="([01])" add="([01])">', replacement_value)
                    if match:
                        text_idx = int(match.group(1))
                        html_before = html_between_replacements_list[text_idx]
                        if html_before is not None:
                            result.append(" " + html_before + " ")
                        else:
                            result.append(" ")
                    else:
                        result.append(" ")
                else:
                    result.append(" ")
        return "".join(result)

    #from hashlib import sha1

    def stringify_raw_text_group(text_group_raw):
        return ''.join(part[0] if part[1] == 0 else f' [ref{part[2]}] ' for part in text_group_raw)

    def stringify_decoded_decoded_raw_text_group(text_group_raw, html_between_replacements_list):
        def decode_replacement(replacement_value, text_idx):
            if not replacement_value.startswith('<html '):
                return " "
            
            match = re.match(r'<html i="([0-9]+)" h="([^"]*)" rme="([01])" add="([01])">', replacement_value)
            if not match:
                return " "
            
            text_idx = int(match.group(1))
            html_before = html_between_replacements_list[text_idx]

            if html_before is None or html_before == "":
                return " "
            
            return f" {html_before} "

        return ''.join(decode_replacement(part[0], part[2]) if part[1] == 1 else part[0] for part in text_group_raw)



    # const textPartsByLang = {};
    text_parts_by_lang = {}
    text_part_raw_list_by_lang = {}

    # loop text_to_translate_list
    # for (const textToTranslate of textToTranslateList)
    for text_to_translate in text_to_translate_list:

        todo_add_to_translations_database = text_to_translate[5]
        if todo_add_to_translations_database == 0:
            # filter. dont send this source text to the translator
            # note: add="${textToTranslate[5]}" is always add="1"
            continue

        # why so complex? why do we wrap text in <html>...</html> tags?
        # because we have two levels of replacements?
        # 1. replace text blocks
        # 2. replace special text parts (html tags, whitespace) in the text blocks
        # also because we send lines to the translator, to get the "splitted" translation
        # so we need a way to encode text blocks

        #print("text_to_translate[3]", repr(text_to_translate[3]))

        # TODO? add source language sl="..."
        text_to_translate_html = f'<html i="{text_to_translate[0]}" h="{text_to_translate[1]}" rme="{text_to_translate[4]}" add="{text_to_translate[5]}">\n{text_to_translate[3]}\n</html>'

        if show_debug:
            print(f"textPart before replace:\n{text_to_translate_html}")

        text_part_replace_regex = re.compile(
            # space before
            r'\s*'
            # symbols in square braces
            # we use this pattern as placeholder for html tags and whitespace
            # so we have to escape existing strings with this pattern
            # 
            r'(?:'
                r'\[ref[' + re.escape(code_num_regex_char_class_import) + r']+\]'
                r'|'
                # replace all newlines
                # to google translate, newline means "new sentence"
                # so extra newlines break the context of words
                r'\n+'
                r'|'
                # html tags
                # this will also replace the added <html> and </html> tags
                r'<.+?>'
                r'|'
                # html entities
                # these can be long...
                # &CounterClockwiseContourIntegral;
                # https://stackoverflow.com/questions/12566098
                r'&[^ ]{2,40};'
            r')'
            # space after
            r'\s*',
            re.S | re.U
        )

        #print("text_to_translate_html", repr(text_to_translate_html))

        # encode html
        # replace html tags with "symbols in square braces"
        # consume all whitespace around the source text
        text_part = text_part_replace_regex.sub(
            lambda match: get_replace(match.group()),
            text_to_translate_html
        )

        text_part_raw_list = []
        last_match_end = 0

        for match in text_part_replace_regex.finditer(text_to_translate_html):
            text_before_match = (
                text_to_translate_html[last_match_end:match.start()]
            )
            #print("text_before_match", __line__(), repr(text_before_match)) # debug
            if text_before_match != "":
                # is_replacement = 0
                text_part_raw_list.append(
                    [text_before_match, 0]
                )

            # see also: get_replace
            replacement_id = replacement_data_lastId_2 + 1
            # is_replacement = 1
            #print("match", __line__(), repr(match.group())) # debug
            text_part_raw_list.append(
                [match.group(), 1, replacement_id]
            )

            last_match_end = match.end()
            replacement_data_lastId_2 += 1

        if show_debug:
            print(f"textPart after replace:\n{text_part}")

        # check 1: sourceText versus textPartRaw
        text_part_actual = stringify_raw_text_group(text_part_raw_list)
        if text_part != text_part_actual:

            print("text_to_translate_html", text_to_translate_html[:100])
            print("text_part", text_part[:100])
            print("text_part_actual", text_part_actual[:100])
            print("text_part_raw_list", text_part_raw_list[:10])
            print("text_part_actual", text_part_actual[:100])

            raise ValueError('FIXME textPart != textPartExpected')

        text_lang = text_to_translate[2]

        text_parts_by_lang.setdefault(text_lang, []).append(text_part)
        text_part_raw_list_by_lang.setdefault(text_lang, []).append(text_part_raw_list)
    # loop text_to_translate_list done

    # const replacementDataPath = inputPath + '.' + inputHtmlHash + '.replacementData.json';
    replacement_data_path = output_dir + f'{input_path}.{input_html_hash}.replacementData.json'
    print(f"writing {replacement_data_path}")
    with open(replacement_data_path, 'w', encoding='utf-8') as f:
        json.dump(replacement_data, f, indent=2)



    # const textGroupsByLang = {};
    text_groups_by_lang = {}
    text_groups_raw_by_source_lang = {}

    # for (const sourceLang of Object.keys(textPartsByLang))
    # loop text_parts_by_lang
    for source_lang in text_parts_by_lang.keys():

        text_parts = text_parts_by_lang[source_lang]
        text_part_raw_list = text_part_raw_list_by_lang[source_lang]

        last_group_size = 0
        decode_num_offset = 0
        decode_num_last_result = 0

        text_groups = ['']
        text_groups_raw = [[]]
        this_group_length = 0

        # loop text_parts
        # for (let textPartsIdx = 0; textPartsIdx < textParts.length; textPartsIdx++)
        for source_lang, text_parts in text_parts_by_lang.items():

            # const textParts = textPartsByLang[source_lang];
            text_part_raw_list = text_part_raw_list_by_lang[source_lang]
            last_group_size = 0
            decode_num_offset = 0
            decode_num_last_result = 0
            text_groups = ['']
            text_groups_raw = [[]]
            this_group_length = 0

            for text_parts_idx in range(len(text_parts)):

                # TODO where do we store all source text parts?
                source_text = text_parts[text_parts_idx]
                text_part_raw = text_part_raw_list[text_parts_idx]

                # check 2: sourceText versus textPartRaw
                # TODO remove?
                source_text_actual = stringify_raw_text_group(text_part_raw)
                if source_text_actual != source_text:
                    raise ValueError("sourceTextActual != sourceText")

                # filter textPart
                # TODO where do we store all source text parts?
                # groups.json and textGroupsRawByLang.json have filtered text parts
                text_part_hash = source_lang + ':' + target_lang + ':' + hashlib.sha1(source_text.encode()).hexdigest()
                if text_part_hash in translations_database:
                    # translation exists in local database
                    # TODO why do we reach this so rarely?
                    # most text parts are still sent to the translator
                    # maybe we sourceText contains dynamic strings (replacement codes)
                    continue

                # TODO why `\n\n<meta attrrrrrrrr="vallll"/>\n\n`
                # sure, the purpose is to make sure
                # that the text group is smaller than charLimit
                # but why do we have to round the length here?

                this_group_length_next = this_group_length + len(source_text)
                
                # TODO remove
                this_group_string = stringify_raw_text_group(text_groups_raw[-1])
                this_group_length_expected = len(this_group_string)
                if this_group_length != this_group_length_expected:
                    raise ValueError("thisGroupLengthExpected != thisGroupLengthExpected")

                # start a new group, move the too-much text-parts to the next group
                if this_group_length_next >= char_limit:
                    text_groups.append('') # TODO remove
                    text_groups_raw.append([])
                    last_group_size = 0 # TODO remove?
                    this_group = text_groups[-1]
                    last_group = text_groups[-2]
                    this_group_raw = text_groups_raw[-1]
                    last_group_raw = text_groups_raw[-2]

                    # dont break sentences across groups
                    # move the end of the last group to the new group
                    # loop replacements, find the first "<div" or "<h3" or "<h2"

                    last_group_end_group_idx = None

                    # TODO check last items of last group
                    # maybe preserve the last group
                    # TODO also look for closing tags? </div> </h1> etc
                    # TODO get htmlBefore

                    # TODO better? when adding text-parts to this group
                    # look for "start of last paragraph or heading"
                    # and keep track of that position
                    # if the current group grows too large
                    # then move the too-much text-parts to the next group
                    # but in theory, this is less efficient
                    # because we have to analyze more text-parts

                    # loop items of last group
                    for last_group_raw_idx in range(len(last_group_raw) - 1, 0, -1):

                        last_group_raw_item = last_group_raw[last_group_raw_idx]

                        if last_group_raw_item[1] == 0:

                            # text node
                            # old code. this would analyze only html nodes
                            # to find "end of sentence"
                            # but this fails on large inline texts
                            # so we also look for "end of sentence" in text nodes

                            text_node_content = last_group_raw_item[0]

                            if text_node_content.endswith(".") and re.search(r'[a-zA-Z]{5,}\.$', text_node_content):
                                # found "end of sentence" in this text node
                                last_group_end_group_idx = last_group_raw_idx
                                break
                            # not found "end of sentence" in this text node
                            continue

                        replacement_id = last_group_raw_item[2]
                        replacement_value = last_group_raw_item[0]

                        if not replacement_value.startswith('<html '):
                            continue

                        # parse text part index from replacementValue
                        match = re.match(r'<html i="([0-9]+)" h="([^"]*)" rme="([01])" add="([01])">', replacement_value)
                        text_idx = int(match.group(1))
                        html_before = html_between_replacements_list[text_idx]

                        if html_before is None:
                            raise ValueError("FIXME more codes than textToTranslateList")
                        
                        if html_before == "":
                            continue
                        
                        # parse last html tag
                        last_tag_start = html_before.rfind("<")
                        last_tag = html_before[last_tag_start:]

                        if last_tag == "":
                            continue

                        # see also: isSentenceTag
                        # assume that all <div> are block elements
                        # so inline elements must be <span> for example <span class="note">
                        if re.match(r'^<\/?(title|h[1-9]|div|li|td)', last_tag):
                            # start of last paragraph or heading
                            last_group_end_group_idx = last_group_raw_idx
                            break
            
                    if last_group_end_group_idx is not None:
                        # stats
                        last_group_size_before = len(stringify_raw_text_group(last_group_raw))
                        this_group_size_before = len(stringify_raw_text_group(this_group_raw))
                        # add text-parts to this group
                        if len(this_group_raw) == 0:
                            this_group_raw.extend(last_group_raw[last_group_end_group_idx + 1:])
                        else:
                            # TODO remove?
                            # TODO is this never reached?
                            raise NotImplementedError("TODO keep this branch")

                        # remove text-parts from last group
                        text_groups_raw[-2] = text_groups_raw[-2][:last_group_end_group_idx + 1]

                        # stats
                        last_group_size_after = len(stringify_raw_text_group(last_group_raw))
                        this_group_size_after = len(stringify_raw_text_group(this_group_raw))

                        # update group length of this group
                        this_group_length_before = this_group_length
                        this_group_length = len(stringify_raw_text_group(this_group_raw))
                        if False:
                            print({
                                "thisGroupLength": this_group_length,
                                "thisGroupLengthBefore": this_group_length_before,
                                "lastGroupSizeBefore": last_group_size_before,
                                "lastGroupSizeAfter": last_group_size_after,
                                "thisGroupSizeBefore": this_group_size_before,
                                "thisGroupSizeAfter": this_group_size_after
                            })
                    else:
                        # last_group_end_group_idx == None
                        #//throw new Error("FIXME lastGroupEndGroupIdx === null");
                        print(f"warning: not moving text-parts of large group {len(text_groups_raw) - 2} with length {len(stringify_raw_text_group(last_group_raw))}")
                        print(f"group {len(text_groups_raw) - 2}:")
                        print("-" * 80)
                        # TODO decode replacements
                        #//console.log(stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 2]));
                        print(stringify_decoded_decoded_raw_text_group(last_group_raw, html_between_replacements_list))
                        print("-" * 80)

                        # TODO remove? thisGroup was not modified
                        # update group length of this group
                        this_group_length_before = this_group_length
                        this_group_length = len(stringify_raw_text_group(this_group_raw))
                        if False:
                            print({
                                "thisGroupLength": this_group_length,
                                "thisGroupLengthBefore": this_group_length_before
                            })

                # add textPart to textGroup

                text_groups_raw[-1].extend(text_part_raw)
                last_group_size += 1 # TODO remove?
                this_group_length += len(source_text)

                # TODO remove
                if False:
                    this_group_string = stringify_raw_text_group(text_groups_raw[-1])
                    this_group_length_expected = len(this_group_string)
                    if this_group_length != this_group_length_expected:
                        raise ValueError("thisGroupLengthExpected != thisGroupLengthExpected")

            text_groups_by_lang[source_lang] = [''.join(part[0] if part[1] == 0 else f' [ref{part[2]}] ' for part in text_group_raw) for text_group_raw in text_groups_raw]
            text_groups_raw_by_source_lang[source_lang] = text_groups_raw

            if show_debug:
                print('\n'.join([f"textGroup {source_lang} {i}:\n{s}\n" for i, s in enumerate(text_groups_by_lang[source_lang])]))

        # loop text_parts end



        # TODO scope?
        # TODO what?
        # const textGroups__newCode = textGroupsRaw.map(textPartRaw => textPartRaw.map(part => {
        text_groups_new_code = [
            ''.join(part[0] if part[1] == 0 else f' [ref{part[2]}] ' for part in text_part_raw)
            for text_part_raw in text_groups_raw
        ]
        text_groups_raw_by_source_lang[source_lang] = text_groups_raw
        text_groups_by_lang[source_lang] = text_groups_new_code
        if show_debug:
            print('\n'.join([f"textGroup {source_lang} {i}:\n{s}\n" for i, s in enumerate(text_groups_new_code)]))
    # loop text_parts_by_lang done



    # Write to textPartsByLang.json
    # const textPartsByLangPath = inputPath + '.' + inputHtmlHash + '.textPartsByLang.json';
    text_parts_by_lang_path = output_dir + f"{input_path}.{input_html_hash}.textPartsByLang.json"
    print(f"Writing {text_parts_by_lang_path}")
    with open(text_parts_by_lang_path, "w") as file:
        json.dump(text_parts_by_lang, file, indent=2)

    # TODO rename to filtered-groups
    # TODO rename to filtered-groups-raw
    # "filtered" as in: these files do not contain texts
    # which are already in the translations database
    # so we dont send them to the translator again

    # Write to textGroupsByLang.json
    text_groups_path = output_dir + f"{input_path}.{input_html_hash}.textGroupsByLang.json"
    print(f"Writing {text_groups_path}")
    with open(text_groups_path, "w") as file:
        json.dump(text_groups_by_lang, file, indent=2)

    # Write to textGroupsRawByLang.json
    text_groups_raw_by_lang_path = output_dir + f"{input_path}.{input_html_hash}.textGroupsRawByLang.json"
    print(f"Writing {text_groups_raw_by_lang_path}")
    with open(text_groups_raw_by_lang_path, "w") as file:
        json.dump(text_groups_raw_by_source_lang, file, indent=2)



    # finally... send the text groups to the translation service
    # FIXME this can fail, then we have to retry
    # so write finished translations to a local database (json? sql?)

    def join_text(text):
        return re.sub(r'( ?\[ref[0-9]+\] ?)+', ' ', text)

    def split_text(text):
        # Translators interpret "\n" as "end of sentence"
        return re.sub(r'( ?\[ref[0-9]+\] ?)+', '\n', text)

    # https://stackoverflow.com/questions/6431061
    def encode_uri_component(text):
        return urllib.parse.quote(text, safe="!~*'()")

    def html_entities_encode(s, quote=True):
        """
        based on python3-3.11.7/lib/python3.11/html/__init__.py
        html.escape would replace '"' with '&quot;'
        but we want '&#x22;'
        like encode of the npm "he" package
        https://www.npmjs.com/package/he
        in: "&<>\"'"
        out: "&#x26;&#x3C;&#x3E;&#x22;&#x27;"

        Replace special characters "&", "<" and ">" to HTML-safe sequences.
        If the optional flag quote is true (the default), the quotation mark
        characters, both double quote (") and single quote (') characters are also
        translated.
        """
        #s = s.replace("&", "&amp;") # Must be done first!
        s = s.replace("&", "&#x26;") # Must be done first!
        #s = s.replace("<", "&lt;")
        s = s.replace("<", "&#x3C;")
        #s = s.replace(">", "&gt;")
        s = s.replace(">", "&#x3E;")
        if quote:
            #s = s.replace('"', "&quot;")
            s = s.replace('"', "&#x22;")
            s = s.replace('\'', "&#x27;")
        return s

    # Generate links
    translate_links = []
    for source_lang in text_groups_by_lang:
        if source_lang == target_lang:
            continue
        for text_group_raw_idx, text_group_raw in enumerate(text_groups_by_lang[source_lang]):
            for export_fn in [join_text, split_text]:
                text_group = export_fn(text_group_raw)
                translate_url = (
                    f"https://translate.google.com/?op=translate&sl={source_lang}&tl={target_lang}&text={encode_uri_component(text_group)}"
                    if translator_name == 'google' else
                    f"https://www.deepl.com/translator#{source_lang}/{target_lang}/{encode_uri_component(text_group)}"
                    if translator_name == 'deepl' else
                    '#invalid-translatorName'
                )
                preview_text = (
                    html_entities_encode(text_group[:preview_text_length//2]) + ' ... ' +
                    html_entities_encode(text_group[-preview_text_length//2:])
                ).replace('\n', ' ')
                link_id = (
                    f"{text_group_raw_idx}-joined" if export_fn == join_text else
                    f"{text_group_raw_idx}-splitted" if export_fn == split_text else
                    f"{text_group_raw_idx}"
                )
                translate_links.append(
                    f'<div id="group-{link_id}">group {link_id}: <a target="_blank" href="{translate_url}">'
                    f"{source_lang}:{target_lang}: {preview_text}</a></div>\n"
                )

    html_src = (
        '<style>' +
        'a:visited { color: green; }' +
        'a { text-decoration: none; }' +
        'a:hover { text-decoration: underline; }' +
        'div { margin-bottom: 1em; }' +
        '</style>\n' +
        '<div id="groups">\n' + ''.join(translate_links) + '</div>\n'
    )

    translate_links_path = output_dir + f"{input_path}.{input_html_hash}.translate-{target_lang}.html"
    print(f"writing {translate_links_path}")
    with open(translate_links_path, 'w', encoding='utf-8') as file:
        file.write(html_src)

    translate_links_path_url = 'file://' + os.path.abspath(translate_links_path)
    print("translate_links_path_url:")
    print(translate_links_path_url)



async def import_lang(input_path, target_lang, translations_path_list, output_dir=""):
    print(f"reading {input_path}")
    with open(input_path, 'r') as file:
        input_html_bytes = file.read()
    input_html_hash = 'sha1-' + hashlib.sha1(input_html_bytes.encode('utf-8')).hexdigest()
    input_path_frozen = output_dir + input_path + '.' + input_html_hash
    output_template_html_path = input_path_frozen + '.outputTemplate.html'
    text_to_translate_list_path = input_path_frozen + '.textToTranslateList.json'
    replacement_data_path = input_path_frozen + '.replacementData.json'
    text_groups_path = input_path_frozen + '.textGroupsByLang.json'
    text_groups_raw_by_lang_path = input_path_frozen + '.textGroupsRawByLang.json'
    html_between_replacements_path = input_path_frozen + '.htmlBetweenReplacementsList.json'
    text_parts_by_lang_path = input_path_frozen + '.textPartsByLang.json'
    translated_html_path = input_path_frozen + '.translated.html'
    translated_splitted_html_path = input_path_frozen + '.translated.splitted.html'
    translations_database_html_path_glob = output_dir + 'translations-google-database-*-*.html'
    translations_database = {}

    for translations_database_html_path in glob.glob(translations_database_html_path_glob):
        print(f"reading {translations_database_html_path}")
        size_before = len(translations_database)
        with open(translations_database_html_path, 'r') as file:
            parse_translations_database(translations_database, file.read())
        size_after = len(translations_database)
        print(f"loaded {size_after - size_before} translations from {translations_database_html_path}")

    input_path_list = [
        input_path_frozen,
        output_template_html_path,
        text_to_translate_list_path,
        replacement_data_path,
        text_groups_path,
        text_groups_raw_by_lang_path,
        text_parts_by_lang_path,
        *translations_path_list,
    ]

    output_path_list = [
        translated_html_path,
        translated_splitted_html_path,
    ]

    for path in output_path_list:
        if os.path.exists(path):
            print(f"error: output file exists: {path}")
            print("hint:")
            print(f"  rm {path}")
            return 1

    for path in input_path_list:
        if not os.path.exists(path):
            print(f"error: missing input file: {path}")
            print("hint: run this script again without the last argument (translations.txt) to rebuild the input files. before that, maybe backup your old input files")
            return 1

    if len(translations_path_list) % 2 != 0:
        last_file = translations_path_list.pop()
        print(f"warning: expecting an even number of translation.txt files in pairs of 'joined' and 'splitted' translations. ignoring the last file: {last_file}")

    print(f"reading {text_groups_raw_by_lang_path}")
    with open(text_groups_raw_by_lang_path, 'r') as file:
        text_groups_raw_by_source_lang = json.load(file)

    print(f"reading {text_to_translate_list_path}")
    with open(text_to_translate_list_path, 'r') as file:
        text_to_translate_list = json.load(file)
        raise "todo"

    translations_path_list.sort()

    print(f"reading {html_between_replacements_path}")
    with open(html_between_replacements_path, 'r') as file:
        html_between_replacements_list = json.load(file)

    print(f"reading {len(translations_path_list)} input files")

    text_group_raw_parsed_list = []

    text_group_raw_parsed = None
    text_group_raw_parsed_idx_last = 0
    text_block_text_part_idx_next = 0
    text_block_text_part_idx_next_last = 0

    print("populating textGroupRawParsedList ...")

    for translated_file_id in range(len(translations_path_list) // 2):

        # this indexing is based on the sort order
        # 00-joined
        # 00-splitted
        # 01-joined
        # 01-splitted

        joined_translations_path = translations_path_list[translated_file_id * 2]
        splitted_translations_path = translations_path_list[translated_file_id * 2 + 1]

        print(f"translatedFileId {translated_file_id}")
        print(f"joinedTranslationsPath {joined_translations_path}")
        print(f"splittedTranslationsPath {splitted_translations_path}")
        print(f"textGroupRawParsedIdxLast {text_group_raw_parsed_idx_last}")

        if not joined_translations_path.endswith("-joined.txt"):
            raise value_error(f"error: not found the '-joined.txt' suffix in joinedTranslationsPath: {joined_translations_path}")
        if not splitted_translations_path.endswith("-splitted.txt"):
            raise value_error(f"error: not found the '-splitted.txt' suffix in splittedTranslationsPath: {splitted_translations_path}")

        translations_base_path = os.path.splitext(joined_translations_path)[0]
        splitted_translations_base_path = os.path.splitext(splitted_translations_path)[0]
        if translations_base_path != splitted_translations_base_path:
            raise value_error("joinedTranslationsBasePath != splittedTranslationsBasePath")

        translations_base_name = os.path.basename(translations_base_path)
        translations_base_name_match = re.match(r'^([a-zA-Z_]+)-([a-zA-Z_]+)-([0-9]+)$', translations_base_name)
        if translations_base_name_match is None:
            raise value_error(f"failed to parse translationsBaseName: {translations_base_name}")
        source_lang, target_lang, translation_file_idx_str = translations_base_name_match.groups()
        translation_file_idx = int(translation_file_idx_str)

        text_group_raw_list = text_groups_raw_by_source_lang.get(source_lang)
        if text_group_raw_list is None:
            raise value_error(f"failed to get textGroupRawList for source_lang {source_lang}")
        if len(text_group_raw_list) != len(text_to_translate_list):
            raise value_error(f"textGroupRawList.len {len(text_group_raw_list)} != textToTranslateList.len {len(text_to_translate_list)} for source_lang {source_lang}")
        text_group_raw = text_group_raw_list[text_group_raw_parsed_idx_last]
        text_group_raw_parsed_idx_last += 1

        if text_group_raw_parsed is None:
            text_group_raw_parsed = parse_text_group_raw(text_group_raw, text_to_translate_list)
            text_group_raw_parsed_list.append(text_group_raw_parsed)
        else:
            if text_group_raw_parsed['textGroupRaw'] != text_group_raw:
                raise value_error("textGroupRawParsedList[-1]['textGroupRaw'] != textGroupRaw")
            if len(text_group_raw_parsed_list) <= text_group_raw_parsed_idx_last:
                raise value_error("textGroupRawParsedList.len <= textGroupRawParsedIdxLast")
            text_group_raw_parsed_list[text_group_raw_parsed_idx_last] = parse_text_group_raw(text_group_raw, text_to_translate_list)

        text_block_text_part_idx_next_last = text_block_text_part_idx_next

        text_block_text_part_idx_next, replacements_count = merge_translations(text_group_raw_parsed, joined_translations_path, splitted_translations_path, text_block_text_part_idx_next)

        print(f"replacementsCount {replacements_count}")

    print("sorting textGroupRawParsedList by keys ...")

    text_group_raw_parsed_list_sorted = sorted(text_group_raw_parsed_list, key=lambda item: item['key'])

    print("writing textPartsByLang ...")

    text_parts_by_lang = {}

    for text_group_raw_parsed in text_group_raw_parsed_list_sorted:
        text_parts_by_lang_item = {
            "inputHtml": text_group_raw_parsed['inputHtml'],
            "inputPath": text_group_raw_parsed['inputPath'],
            "inputPathFrozen": text_group_raw_parsed['inputPathFrozen'],
            "outputTemplateHtml": text_group_raw_parsed['outputTemplateHtml'],
            "outputTemplatePath": text_group_raw_parsed['outputTemplatePath'],
            "textPartsByLang": text_group_raw_parsed['textPartsByLang'],
            "textToTranslateList": text_group_raw_parsed['textToTranslateList'],
        }
        key = text_group_raw_parsed['key']
        if key in text_parts_by_lang:
            raise value_error(f"error: key '{key}' already exists in textPartsByLang")
        text_parts_by_lang[key] = text_parts_by_lang_item

    with open(text_parts_by_lang_path, 'w') as file:
        json.dump(text_parts_by_lang, file, indent=4, ensure_ascii=False)

    print(f"writing {translated_splitted_html_path} ...")

    with open(translated_splitted_html_path, 'wb') as file:
        file.write(text_group_raw_parsed_list_sorted[0]['inputHtml'])

    print(f"writing {translated_html_path} ...")

    with open(translated_html_path, 'wb') as file:
        for text_group_raw_parsed in text_group_raw_parsed_list_sorted:
            output_html = substitute_translations(text_group_raw_parsed)
            file.write(output_html)

    print(f"done: output html files: {translated_html_path} {translated_splitted_html_path}")
    return 0



def parse_translations_database(translations_database, translations_database_text):
    def sha1sum(text):
        return 'sha1-' + hashlib.sha1(text.encode('utf-8')).hexdigest()

    def replace_callback(match):
        translation_key, source_text, translated_text = match.groups()
        source_lang, target_lang, source_hash = translation_key.split(":")
        source_hash_actual = sha1sum(source_text)
        if source_hash != source_hash_actual:
            print(f"error: parseTranslationsDatabase: sourceHash != sourceHashActual: {source_hash} != {source_hash_actual}: sourceText = {source_text[:100]} ...", file=sys.stderr)
            raise value_error("fixme")
        translations_database[translation_key] = [source_text, translated_text]
        return ""

    translations_database_text = re.sub(
        r'\n<h2 id="[^"]+">([^<]+)<\/h2>\n<table style="width:100%"><tr>\n<td style="width:50%"><pre style="white-space:pre-wrap">\n(.*?)\n<\/pre><\/td>\n<td style="width:50%"><pre style="white-space:pre-wrap">\n(.*?)\n<\/pre><\/td>\n<\/tr><\/table>\n',
        replace_callback,
        translations_database_text,
        flags=re.s
    )

    if not translations_database_text.startswith('<h1>translations database'):
        print("warning: parseTranslationsDatabase did not parse all input. rest:", translations_database_text, file=sys.stderr)



async def main():
    lang_map = {
        # simplified chinese
        'zh': 'zh-CN',
    }

    def get_lang(string):
        return lang_map.get(string) or string

    argv = sys.argv[1:]

    input_path = argv[0] if argv else None

    target_lang = get_lang(argv[1]) if len(argv) > 1 else None

    translations_path_list = argv[2:]

    # TODO implement. use argparse
    #output_dir = (os.path.abspath(argv[2]) + "/") if len(argv) > 2 else ""
    output_dir = ""

    if not input_path or not target_lang:
        print("error: missing arguments", file=sys.stderr)
        print("usage:", file=sys.stderr)
        print("# step 1: export text parts to a html file with links to translator", file=sys.stderr)
        print("python translate-richtext.py input.html en", file=sys.stderr)
        print("# step 2: import the translated text parts from a text file", file=sys.stderr)
        print("python translate-richtext.py input.html en translations.txt", file=sys.stderr)
        return 1

    if translations_path_list:
        return await import_lang(input_path, target_lang, translations_path_list, output_dir)
    else:
        return await export_lang(input_path, target_lang, output_dir)



if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
