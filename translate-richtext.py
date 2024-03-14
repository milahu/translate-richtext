#!/usr/bin/env python3

# FIXME translations_db_set is never called
# $ sqlite3 translations-cache.db "select count(1) from translations_cache" 
# 0

# TODO export_lang must decode html entities to utf8
# TODO import_lang must encode html entities from utf8

# fixed: leading and trailing whitespace is lost when it should be part of text nodes
# this gives a different result than translate-richtext.js
# https://github.com/tree-sitter/tree-sitter-html/issues/87
# fixed in
# https://github.com/tree-sitter/tree-sitter-html/pull/89

import os
import sys
import re
import glob
import io
import json
import shutil
import hashlib
import subprocess
import html
import urllib.parse
import ast
import asyncio
import sqlite3

import tree_sitter_languages

# TODO? use aiohttp_chromium
from selenium_driverless import webdriver
from selenium_driverless.types.by import By



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

        node_text = json_dumps(node_source)
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

#print("enum_ts_symbol_identifiers =", json_dumps(enum_ts_symbol_identifiers, indent=2))
#print("char_ts_symbol_names =", json_dumps(char_ts_symbol_names, indent=2))

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
    #print("full_node_kind =", json_dumps(full_node_kind, indent=2))
    print("node_kind =", json_dumps(node_kind, indent=2))
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



# fs.writeFileSync
def write_file(file_path, content):
    with open(file_path, 'w') as file:
        file.write(content)



# JSON.stringify
def json_dumps(obj):
    return json.dumps(obj, ensure_ascii=False, separators=(',', ':'))



# no: TypeError: Object of type RandomWriteList is not JSON serializable
#import collections
#class RandomWriteList(collections.UserList):

# https://stackoverflow.com/a/78147717/10440128

class RandomWriteList(list):
    "list with random write access, like Array in javascript"
    def __setitem__(self, idx, val):
        try:
            super().__setitem__(idx, val)
        except IndexError:
            self += [None] * (idx - len(self))
            self.append(val)

# L = RandomWriteList()
# L[2] = "2"
# L[5] = "5"
# print("L", repr(L))
# assert L == [None, None, '2', None, None, '5']



class TranslationsDB():

    def __init__(self, path):

        self.path = path
        self.con = sqlite3.connect(self.path)
        self.cur = self.con.cursor()

        self.create_table_source_text()
        self.create_table_target_text()

    def __del__(self):
        self.con.commit()
        self.con.close()

    def create_table_source_text(self):

        # populated by export_lang
        table_name = "source_text"
        sql_query = (
            f"CREATE TABLE {table_name} (\n"
            "  id INTEGER PRIMARY KEY,\n"
            #"  key TEXT,\n" TODO? unique translation_key: source_lang + target_lang + source_text_hash
            "  source_lang TEXT,\n"
            "  source_text_hash TEXT,\n"
            #"  source_text_hash BLOB,\n"
            "  source_text TEXT,\n"
            "  UNIQUE (source_lang, source_text_hash)\n"
            ")"
        )
        try:
            self.cur.execute(sql_query)
        except sqlite3.OperationalError as exc:
            if exc.args[0] != f"table {table_name} already exists":
                raise

    def create_table_target_text(self):

        # populated by import_lang
        table_name = "target_text"
        sql_query = (
            f"CREATE TABLE {table_name} (\n"
            "  id INTEGER PRIMARY KEY,\n"
            "  source_text_id INTEGER,\n"
            # TODO with multiple translators, use separate tables for source_text and target_text
            "  target_lang TEXT,\n"
            "  translator_name TEXT,\n"
            "  target_text TEXT,\n"
            "  target_text_splitted TEXT,\n"
            "  UNIQUE (source_text_id, target_lang, translator_name)\n"
            ")"
        )
        try:
            self.cur.execute(sql_query)
        except sqlite3.OperationalError as exc:
            if exc.args[0] != f"table {table_name} already exists":
                raise

    def add_source_text(self, source_lang, source_text_hash, source_text):

        # note: this throws if xxx exists
        sql_query = (
            "INSERT INTO source_text ("
            "  source_lang, source_text_hash, source_text"
            ") VALUES ("
            "  ?, ?, ?"
            ")"
        )
        sql_args = (source_lang, source_text_hash, source_text)
        try:
            self.cur.execute(sql_query, sql_args)
            #source_text_id = self.cur.lastrowid
            #return source_text_id
        except sqlite3.IntegrityError:
            # UNIQUE constraint failed: source_text.source_lang, source_text.source_text_hash
            pass

    def get_source_text_id(self, source_lang, source_text_hash):

        sql_query = (
            "SELECT id FROM source_text WHERE "
            "source_lang = ? AND source_text_hash = ? "
            "LIMIT 1"
        )
        sql_args = (source_lang, source_text_hash)
        row = self.cur.execute(sql_query, sql_args).fetchone()
        if row == None:
            return None
        return row[0]

    def add_target_text(self, source_lang, source_text_hash, target_lang, translator_name, target_text, target_text_splitted):

        # note: this throws if xxx exists
        source_text_id = self.get_source_text_id(source_lang, source_text_hash)
        sql_query = (
            "INSERT INTO target_text ("
            "  source_text_id, target_lang, translator_name, target_text, target_text_splitted"
            ") VALUES ("
            "  ?, ?, ?, ?, ?"
            ")"
        )
        sql_args = (source_text_id, target_lang, translator_name, target_text, target_text_splitted)
        self.cur.execute(sql_query, sql_args)

    #def has_target_text(self, source_lang, target_lang, source_text_hash):
    def has_target_text(self, source_lang, source_text_hash, target_lang, translator_name=None):

        source_text_id = self.get_source_text_id(source_lang, source_text_hash)
        if source_text_id == None:
            return False
        sql_query = (
            "SELECT 1 FROM target_text WHERE "
            "source_text_id = ? AND target_lang = ? " +
            ("AND translator_name = ? " if translator_name else "") +
            "LIMIT 1"
        )
        sql_args = [source_text_id, target_lang]
        if translator_name:
            sql_args.append(translator_name)
        return self.cur.execute(sql_query, sql_args).fetchone() != None

    #def get_target_text_list(self, source_lang, target_lang, source_text_hash):
    def get_target_text(self, source_lang, source_text_hash, target_lang, translator_name):

        "get target_text from one translator"

        source_text_id = self.get_source_text_id(source_lang, source_text_hash)
        if source_text_id == None:
            return False
        sql_query = (
            "SELECT target_text, target_text_splitted FROM target_text WHERE "
            "source_text_id = ? AND target_lang = ? AND translator_name = ? "
            "LIMIT 1"
        )
        sql_args = (source_text_id, target_lang, translator_name)
        return self.cur.execute(sql_query, sql_args).fetchone()

    #def get_target_text_list(self, source_lang, target_lang, source_text_hash):
    def get_target_text_list(self, source_lang, source_text_hash, target_lang):

        "get target_text from all translators"

        source_text_id = self.get_source_text_id(source_lang, source_text_hash)
        if source_text_id == None:
            return False
        sql_query = (
            "SELECT translator_name, target_text, target_text_splitted FROM target_text WHERE "
            "source_text_id = ? AND target_lang = ? "
        )
        sql_args = (source_text_id, target_lang)
        return self.cur.execute(sql_query, sql_args).fetchall()



# global state
translations_db = None



async def export_lang(input_path, target_lang, output_dir=""):

    global translations_db

    # tree-sitter expects binary string
    #with open(input_path, 'r') as f:
    with open(input_path, 'rb') as f:
        input_html_bytes = f.read()
    input_html_hash = 'sha1-' + hashlib.sha1(input_html_bytes).hexdigest()

    # TODO rename input_path_frozen to output_base
    #output_base = output_dir + f"{input_path}.{input_html_hash}"
    #input_path_frozen = output_dir + input_path + '.' + input_html_hash
    output_dir = os.path.join(os.path.dirname(input_path), output_dir)
    input_path_frozen = output_dir + os.path.basename(input_path) + '.' + input_html_hash

    print(f'writing {input_path_frozen}')
    with open(input_path_frozen, 'wb') as f:
        f.write(input_html_bytes)

    if not translations_db:
        translations_db = TranslationsDB(output_dir + "translations-cache.db")

    # TODO use self.cur
    # translations_database_html_path_glob = output_dir + 'translations-google-database-*-*.html'
    # translations_database = {}

    # # parse translation databases
    # print("parsing translation databases")
    # for translations_database_html_path in glob.glob(translations_database_html_path_glob):
    #     print(f'reading {translations_database_html_path}')
    #     with open(translations_database_html_path, 'r') as f:
    #         parse_translations_database(translations_database, f.read())

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

            node_text = json_dumps(node_source)
            if len(node_text) > max_len:
                node_text = node_text[0:max_len] + "..."

            space_node_text = json_dumps(input_html_bytes[last_node_to:node.range.end_byte].decode("utf8"))
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
            current_tag.lang != target_lang
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

    #print("walk_html_tree")

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

                            attr_value_hash_bytes = hashlib.sha1(attr_value.encode("utf8")).digest()
                            attr_value_hash = attr_value_hash_bytes.hex()
                            text_idx = len(text_to_translate_list)
                            node_source_key = f"{text_idx}_{current_lang}_{attr_value_hash}"
                            todo_remove_end_of_sentence = 0

                            if not node_source_is_end_of_sentence(attr_value):
                                attr_value += "."
                                todo_remove_end_of_sentence = 1

                            # translation_key = f"{current_lang}:{target_lang}:{attr_value_hash}"

                            has = translations_db.has_target_text(
                                current_lang,
                                attr_value_hash,
                                target_lang,
                                translator_name
                            )

                            if not has:
                                translations_db.add_source_text(
                                    current_lang,
                                    attr_value_hash,
                                    attr_value
                                )

                            # fix: KeyError: 'en' @ text_groups_raw_by_source_lang[source_lang]
                            todo_add_to_translations_database = 0 if has else 1
                            #todo_add_to_translations_database = 1

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
                node_source_trimmed_hash_bytes = hashlib.sha1(node_source_trimmed.encode()).digest()
                node_source_trimmed_hash = node_source_trimmed_hash_bytes.hex()
                text_idx = len(text_to_translate_list)
                node_source_key = f"{text_idx}_{current_lang}_{node_source_trimmed_hash}"
                todo_remove_end_of_sentence = 0

                # no. one node can have multiple text child nodes
                # example: Text EntityReference Text
                # fix: add "." only before StartCloseTag
                #if not node_source_is_end_of_sentence(node_source_trimmed) and is_sentence_tag(current_tag):
                #    node_source_trimmed += "."
                #    todo_remove_end_of_sentence = 1

                #translation_key = f"{current_lang}:{target_lang}:{node_source_trimmed_hash}"

                has = translations_db.has_target_text(
                    current_lang,
                    node_source_trimmed_hash,
                    target_lang,
                    translator_name
                )

                if not has:
                    translations_db.add_source_text(
                        current_lang,
                        node_source_trimmed_hash,
                        node_source_trimmed
                    )

                # fix: KeyError: 'en' @ text_groups_raw_by_source_lang[source_lang]
                todo_add_to_translations_database = 0 if has else 1
                #todo_add_to_translations_database = 1

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
                node_source_trimmed_hash_bytes = hashlib.sha1(node_source_trimmed.encode()).digest()
                node_source_trimmed_hash = node_source_trimmed_hash_bytes.hex()
                text_idx = len(text_to_translate_list)
                node_source_key = f"{text_idx}_{comment_lang or current_lang}_{node_source_trimmed_hash}"
                todo_remove_end_of_sentence = 0

                if (
                    not node_source_is_end_of_sentence(node_source_trimmed) and
                    is_sentence_tag(current_tag)
                ):
                    node_source_trimmed += "."
                    todo_remove_end_of_sentence = 1

                #translation_key = f"{current_lang}:{target_lang}:{node_source_trimmed_hash}"

                has = translations_db.has_target_text(
                    current_lang,
                    node_source_trimmed_hash,
                    target_lang,
                    translator_name
                )

                if not has:
                    translations_db.add_source_text(
                        current_lang,
                        node_source_trimmed_hash,
                        node_source_trimmed
                    )

                # fix: KeyError: 'en' @ text_groups_raw_by_source_lang[source_lang]
                todo_add_to_translations_database = 0 if has else 1
                #todo_add_to_translations_database = 1

                if current_lang is None:
                    source_start = node_source[:100]
                    # TODO show "outerHTML". this is only the text node
                    raise ValueError(f"node has no lang attribute: {repr(source_start)}")

                text_to_translate = (
                    text_idx,
                    node_source_trimmed_hash,
                    current_lang,
                    node_source_trimmed,
                    todo_remove_end_of_sentence,
                    # FIXME filter
                    todo_add_to_translations_database,
                )

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
        json.dump(text_to_translate_list, f, indent=2, ensure_ascii=False)

    html_between_replacements_path = output_dir + input_path + '.' + input_html_hash + '.htmlBetweenReplacementsList.json'
    print(f"writing {html_between_replacements_path}")
    with open(html_between_replacements_path, 'w') as f:
        json.dump(html_between_replacements_list, f, indent=2, ensure_ascii=False)

    # TODO build chunks of same language
    # limited by charLimit = 5000

    # new code -> old code
    # textToTranslateList -> textParts

    # const replacementData = {};
    replacement_data = {}
    replacement_data['replacementList'] = {}
    replacement_data['lastId'] = -1
    replacement_data_lastId_2 = -1



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

        (
            text_idx,
            node_source_trimmed_hash,
            current_lang,
            node_source_trimmed,
            todo_remove_end_of_sentence,
            # FIXME filter
            todo_add_to_translations_database,
        ) = text_to_translate

        if todo_add_to_translations_database == 0:
            # filter. dont send this source text to the translator
            # note: add="${textToTranslate[5]}" is always add="1"
            continue

        # FIXME filter
        assert todo_add_to_translations_database == 0

        # why so complex? why do we wrap text in <html>...</html> tags?
        # because we have two levels of replacements?
        # 1. replace text blocks
        # 2. replace special text parts (html tags, whitespace) in the text blocks
        # also because we send lines to the translator, to get the "splitted" translation
        # so we need a way to encode text blocks

        #print("text_to_translate[3]", repr(text_to_translate[3]))

        # TODO? add source language sl="..."
        text_to_translate_html = (
            f'<html i="{text_idx}" '
            f'h="{node_source_trimmed_hash}" '
            f'rme="{todo_remove_end_of_sentence}" '
            f'add="{todo_add_to_translations_database}"'
            f'>\n{node_source_trimmed}\n</html>'
        )

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

        # FIXME filter: text_parts_by_lang text_part_raw_list_by_lang
        # FIXME filter: text_part text_part_raw_list

        text_parts_by_lang.setdefault(text_lang, []).append(text_part)
        text_part_raw_list_by_lang.setdefault(text_lang, []).append(text_part_raw_list)
    # loop text_to_translate_list done

    # const replacementDataPath = inputPath + '.' + inputHtmlHash + '.replacementData.json';
    replacement_data_path = output_dir + f'{input_path}.{input_html_hash}.replacementData.json'
    print(f"writing {replacement_data_path}")
    with open(replacement_data_path, 'w') as f:
        json.dump(replacement_data, f, indent=2, ensure_ascii=False)



    # const textGroupsByLang = {};
    text_groups_by_lang = {}
    text_groups_raw_by_source_lang = {}

    # for (const sourceLang of Object.keys(textPartsByLang))
    # loop text_parts_by_lang
    for source_lang in text_parts_by_lang.keys():

        # last_group_size = 0
        # decode_num_offset = 0
        # decode_num_last_result = 0

        #text_groups = ['']
        #text_groups_raw = [[]]
        #this_group_length = 0

        # FIXME filter: text_part_list text_part_raw_list
        # FIXME filter: text_parts_by_lang text_part_raw_list_by_lang

        # loop text_part_list
        # for (let textPartsIdx = 0; textPartsIdx < textParts.length; textPartsIdx++)
        for source_lang, text_part_list in text_parts_by_lang.items():

            # TODO replace text_part_list with text_part_raw_list
            # const textParts = textPartsByLang[source_lang];
            text_part_raw_list = text_part_raw_list_by_lang[source_lang]

            last_group_size = 0
            decode_num_offset = 0
            decode_num_last_result = 0

            text_groups = ['']
            text_groups_raw = [[]]
            this_group_length = 0

            for text_part_idx in range(len(text_part_list)):

                # note: text_part != source_text
                # text_part " [ref0] who are my friends, [ref1] team composition, [ref2] matchmaking ...
                # source_text "who are my friends,"

                # TODO where do we store all source text parts?
                # FIXME filter: text_part_list text_part_raw_list
                # TODO? remove text_part_list, use only text_part_raw_list
                text_part = text_part_list[text_part_idx]
                text_part_raw = text_part_raw_list[text_part_idx]

                # check 2: sourceText versus textPartRaw
                # TODO remove?
                text_part_actual = stringify_raw_text_group(text_part_raw)
                if text_part_actual != text_part:
                    raise ValueError("sourceTextActual != sourceText")

                # filter textPart
                # TODO where do we store all source text parts?
                # groups.json and textGroupsRawByLang.json have filtered text parts
                text_part_hash_bytes = hashlib.sha1(text_part.encode()).digest()
                text_part_hash = text_part_hash_bytes.hex()
                #text_part_hash = source_lang + ':' + target_lang + ':' + hashlib.sha1(text_part.encode()).hexdigest()
                #if text_part_hash in translations_database:

                # text_part is not stored in the source_text table
                # so translations_db.has_target_text always returns false
                # no. fix: KeyError: 'en' @ text_groups_raw_by_source_lang[source_lang]
                # has = translations_db.has_target_text(
                #     source_lang,
                #     text_part_hash,
                #     target_lang,
                #     translator_name
                # )
                # if has:
                #     # translation exists in local database
                #     # TODO why do we reach this so rarely?
                #     # most text parts are still sent to the translator
                #     # maybe we sourceText contains dynamic strings (replacement codes)
                #     continue

                # print("not has", (
                #     source_lang,
                #     text_part_hash,
                #     target_lang,
                #     translator_name
                # ))
                # not has (None, '313e7259db63ff5908d388d7289bcb1eaf2b23ec', 'de', 'google')

                #print("text_part", json_dumps(text_part))
                # FIXME use translated parts from db: "who are my friends,"
                # FIXME filter: text_part_list text_part_raw_list
                # text_part " [ref0] who are my friends, [ref1] team composition, [ref2] matchmaking ...

                # TODO why `\n\n<meta attrrrrrrrr="vallll"/>\n\n`
                # sure, the purpose is to make sure
                # that the text group is smaller than charLimit
                # but why do we have to round the length here?

                this_group_length_next = this_group_length + len(text_part)

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
                this_group_length += len(text_part)

            text_groups_by_lang[source_lang] = [
                ''.join(
                    part[0] if part[1] == 0 else f' [ref{part[2]}] ' for part in text_group_raw
                ) for text_group_raw in text_groups_raw
            ]

            text_groups_raw_by_source_lang[source_lang] = text_groups_raw

            if show_debug:
                print('\n'.join([f"textGroup {source_lang} {i}:\n{s}\n" for i, s in enumerate(text_groups_by_lang[source_lang])]))

        # loop text_part_list end



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
    print(f"writing {text_parts_by_lang_path}")
    with open(text_parts_by_lang_path, "w") as file:
        json.dump(text_parts_by_lang, file, indent=2, ensure_ascii=False)

    # TODO rename to filtered-groups
    # TODO rename to filtered-groups-raw
    # "filtered" as in: these files do not contain texts
    # which are already in the translations database
    # so we dont send them to the translator again

    # Write to textGroupsByLang.json
    text_groups_path = output_dir + f"{input_path}.{input_html_hash}.textGroupsByLang.json"
    print(f"writing {text_groups_path}")
    with open(text_groups_path, "w") as file:
        json.dump(text_groups_by_lang, file, indent=2, ensure_ascii=False)

    # Write to textGroupsRawByLang.json
    text_groups_raw_by_lang_path = output_dir + f"{input_path}.{input_html_hash}.textGroupsRawByLang.json"
    print(f"writing {text_groups_raw_by_lang_path}")
    with open(text_groups_raw_by_lang_path, "w") as file:
        json.dump(text_groups_raw_by_source_lang, file, indent=2, ensure_ascii=False)

    # TODO interleave joined and splitted texts more fine-grained
    # produce a stream of sentences: joined, splitted, joined, splitted, ...

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
    translate_url_list = []
    #translate_links = []
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
                # preview_text = (
                #     html_entities_encode(text_group[:preview_text_length//2]) + ' ... ' +
                #     html_entities_encode(text_group[-preview_text_length//2:])
                # ).replace('\n', ' ')
                # 04d: zero-pad ids to 0001 etc -> sort is numeric sort
                # see also translations_base_name_match
                link_id = f"translation-{source_lang}-{target_lang}-{text_group_raw_idx:04d}" + (
                    f"-joined" if export_fn == join_text else
                    f"-splitted" if export_fn == split_text else
                    f""
                )
                translate_item = (link_id, translate_url)
                translate_url_list.append(translate_item)
                # translate_links.append(
                #     f'<div id="group-{link_id}">group {link_id}: <a target="_blank" href="{translate_url}">'
                #     f"{source_lang}:{target_lang}: {preview_text}</a></div>\n"
                # )

    # html_src = (
    #     '<style>' +
    #     'a:visited { color: green; }' +
    #     'a { text-decoration: none; }' +
    #     'a:hover { text-decoration: underline; }' +
    #     'div { margin-bottom: 1em; }' +
    #     '</style>\n' +
    #     '<div id="groups">\n' + ''.join(translate_links) + '</div>\n'
    # )

    # translate_links_path = output_dir + f"{input_path}.{input_html_hash}.translate-{target_lang}.html"
    # print(f"writing {translate_links_path}")
    # with open(translate_links_path, 'w') as file:
    #     file.write(html_src)

    # translate_links_path_url = 'file://' + os.path.abspath(translate_links_path)
    # print("translate_links_path_url:")
    # print(translate_links_path_url)

    translate_url_list_path = input_path_frozen + f".translateUrlList-{target_lang}.json"
    print(f"writing {translate_url_list_path}")
    with open(translate_url_list_path, 'w') as file:
        json.dump(translate_url_list, file, indent=2, ensure_ascii=False)

    return input_path_frozen



#async def import_lang(input_path, target_lang, translations_path_list, output_dir=""):
#async def import_lang(input_path, target_lang, output_dir, translations_path_list=None):
async def import_lang(input_path, target_lang, output_dir, translations_path_list):

    global translations_db

    if not translations_db:
        translations_db = TranslationsDB(output_dir + "translations-cache.db")

    print(f"reading {input_path}")
    with open(input_path, 'r') as file:
        input_html_bytes = file.read()
    input_html_hash = 'sha1-' + hashlib.sha1(input_html_bytes.encode('utf-8')).hexdigest()

    output_dir = os.path.join(os.path.dirname(input_path), output_dir)

    if input_path.endswith(input_html_hash):
        # input path is already frozen
        input_path_frozen = input_path
    else:
        #input_path_frozen = output_dir + input_path + '.' + input_html_hash
        input_path_frozen = output_dir + os.path.basename(input_path) + '.' + input_html_hash

    output_template_html_path = input_path_frozen + '.outputTemplate.html'
    text_to_translate_list_path = input_path_frozen + '.textToTranslateList.json'
    replacement_data_path = input_path_frozen + '.replacementData.json'
    text_groups_path = input_path_frozen + '.textGroupsByLang.json'
    text_groups_raw_by_lang_path = input_path_frozen + '.textGroupsRawByLang.json'
    html_between_replacements_path = input_path_frozen + '.htmlBetweenReplacementsList.json'
    text_parts_by_lang_path = input_path_frozen + '.textPartsByLang.json'
    translated_html_path = input_path_frozen + f'.translated-{target_lang}.html'
    translated_splitted_html_path = input_path_frozen + f'.translated-{target_lang}.splitted.html'

    # TODO use self.cur
    # translations_database_html_path_glob = output_dir + 'translations-google-database-*-*.html'
    # translations_database = {}

    # for translations_database_html_path in glob.glob(translations_database_html_path_glob):
    #     print(f"reading {translations_database_html_path}")
    #     size_before = len(translations_database)
    #     with open(translations_database_html_path, 'r') as file:
    #         parse_translations_database(translations_database, file.read())
    #     size_after = len(translations_database)
    #     print(f"loaded {size_after - size_before} translations from {translations_database_html_path}")

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
        #raise "todo"

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

    # loop input files: add source and translated text parts to textGroupRawParsed 
    for translated_file_id in range(len(translations_path_list) // 2):

        if debug_alignment:
            # console.log(`translatedFileId ${String(translatedFileId).padStart(5)}`);
            print(f"translatedFileId {translated_file_id:5d}")

        # this indexing is based on the sort order
        # 0000-joined
        # 0000-splitted
        # 0001-joined
        # 0001-splitted

        joined_translations_path = translations_path_list[translated_file_id * 2]
        splitted_translations_path = translations_path_list[translated_file_id * 2 + 1]

        #print(f"textGroupRawParsedIdxLast {text_group_raw_parsed_idx_last}")

        #print(f"joinedTranslationsPath {joined_translations_path}")
        #print(f"splittedTranslationsPath {splitted_translations_path}")

        if not joined_translations_path.endswith("-joined.txt"):
            raise ValueError(f"error: not found the '-joined.txt' suffix in joinedTranslationsPath: {joined_translations_path}")
        if not splitted_translations_path.endswith("-splitted.txt"):
            raise ValueError(f"error: not found the '-splitted.txt' suffix in splittedTranslationsPath: {splitted_translations_path}")

        translations_base_path = joined_translations_path[:(-1 * len("-joined.txt"))]
        splitted_translations_base_path = splitted_translations_path[:(-1 * len("-splitted.txt"))]
        if translations_base_path != splitted_translations_base_path:
            print(f"joinedTranslationsBasePath {translations_base_path}")
            print(f"splittedTranslationsBasePath {splitted_translations_base_path}")
            raise ValueError("joinedTranslationsBasePath != splittedTranslationsBasePath")

        # example: xxx.translation-en-de-0001
        translations_base_name = os.path.basename(translations_base_path)
        translations_base_name_match = re.search(r"\.translation-([a-z_]+)-([a-z_]+)-([0-9]{4})$", translations_base_name)
        if translations_base_name_match is None:
            raise ValueError(f"failed to parse translationsBaseName: {translations_base_name}")
        source_lang, target_lang, translation_file_idx_str = translations_base_name_match.groups()
        translation_file_idx = int(translation_file_idx_str)

        # FIXME KeyError: 'en' @ text_groups_raw_by_source_lang[source_lang]
        # const textGroupRawList = textGroupsRawBySourceLang[sourceLang][translationFileIdx];
        text_group_raw_list = text_groups_raw_by_source_lang[source_lang][translation_file_idx]

        debug_text_group_raw_parser = True # TODO move up
        debug_text_group_raw_parser = False # TODO move up

        # add values to textGroupRawParsed.text_block_text_part_list
        # parse text groups = source text blocks
        # each source text block is identified by its sourceTextBlockHash
        # TODO rename text_group_raw to text_part_node
        for text_group_raw in text_group_raw_list:
            if debug_text_group_raw_parser:
                print("text_group_raw", repr(text_group_raw))
            if text_group_raw[1] == 1:
                # Replacement: <html> or </html> or whitespace (or other HTML code?)
                if text_group_raw[0].startswith('<html '):
                    # Start of block
                    # Parse HTML tag attributes
                    if debug_text_group_raw_parser:
                        print("text_group_raw[0]", repr(text_group_raw[0]))
                    (
                        source_text_block_idx,
                        source_text_block_hash,
                        todo_remove_end_of_sentence,
                        todo_add_to_translations_database,
                        whitespace_before_first_text_part,
                    ) = re.match(
                        r'^<html i="([0-9]+)" h="([^"]*)" rme="([01])" add="([01])">\n(.*)$',
                        text_group_raw[0],
                        re.DOTALL
                    ).groups()

                    source_text_block_idx = int(source_text_block_idx)
                    todo_remove_end_of_sentence = int(todo_remove_end_of_sentence)
                    todo_add_to_translations_database = int(todo_add_to_translations_database)

                    if source_text_block_hash == "":
                        # TODO handle empty source_text_block_hash
                        pass
                    if todo_remove_end_of_sentence == 1:
                        # TODO handle todo_remove_end_of_sentence == 1
                        pass

                    text_group_raw_parsed_new = {
                        # FIXME? camelCase for js compat
                        "translated_file_id": translated_file_id,
                        "source_text_block_idx": source_text_block_idx,
                        "source_text_block_hash": source_text_block_hash,
                        # TODO translation_line_list = RandomWriteList()
                        "text_block_text_part_list": RandomWriteList([whitespace_before_first_text_part]),
                        # TODO translation_line_list = RandomWriteList()
                        "text_block_text_part_is_text_list": RandomWriteList([False]),
                        "todo_remove_end_of_sentence": todo_remove_end_of_sentence,
                        "todo_add_to_translations_database": todo_add_to_translations_database,
                        "translations": {
                            # TODO add more translations
                            # TODO translation_line_list = RandomWriteList()
                            "splittedTranslationLineList": RandomWriteList(),
                            "joinedTranslationLineList": RandomWriteList(),
                        }
                    }

                    text_group_raw_parsed_list.append(text_group_raw_parsed_new)
                    text_group_raw_parsed = text_group_raw_parsed_new

                # else if (textGroupRaw[0].endsWith("\n</html>"))
                elif text_group_raw[0].endswith("\n</html>"):
                    # end of block

                    # TODO handle todoRemoveEndOfSentence == 1 (here?)
                    # 8 == len("\n</html>")
                    whitespace_after_last_text_part = text_group_raw[0][:-8]
                    debug_text_group_raw_parser = True # TODO move up
                    debug_text_group_raw_parser = False # TODO move up
                    # TODO text_group_raw[0]
                    if debug_text_group_raw_parser:
                        print("text_group_raw", repr(text_group_raw))
                        print("whitespace_after_last_text_part", repr(whitespace_after_last_text_part))
                    text_group_raw_parsed["text_block_text_part_list"].append(whitespace_after_last_text_part)
                    text_group_raw_parsed["text_block_text_part_is_text_list"].append(False)
                    # TODO later: add whitespace to translations

                    if text_group_raw_parsed["todo_remove_end_of_sentence"] == 1:

                        text_block_text_part_list = text_group_raw_parsed["text_block_text_part_list"]

                        idx = len(text_block_text_part_list) - 1
                        if whitespace_after_last_text_part == "":
                            # "." is in previous text part. TODO why? this was working before...
                            idx = idx - 1
                        if debug_alignment:
                            print("3000 textBlockTextPartList[idx]", json_dumps(text_block_text_part_list[idx]))
                        end = text_block_text_part_list[idx][-1]
                        if end != ".":
                            # unexpected end
                            raise ValueError(f"unexpected end: {end}")
                        # remove last char
                        text_block_text_part_list[idx] = text_block_text_part_list[idx][:-1]
                    text_group_raw_parsed = None

                else:
                    #if text_group_raw[0].match(r'^\s+$') is None:
                    if re.match(r'^\s+$', text_group_raw[0]) == None:
                        # Unexpected replacement
                        raise ValueError(f"Unexpected replacement: {json_dumps(text_group_raw[0])}")
                    # Whitespace. Usually this is indent of lines
                    whitespace_between_parts = text_group_raw[0]
                    text_group_raw_parsed["text_block_text_part_list"].append(whitespace_between_parts)
                    text_group_raw_parsed["text_block_text_part_is_text_list"].append(False)
            else:
                # Add text part to text block
                text_group_raw_parsed["text_block_text_part_list"].append(text_group_raw[0])
                text_group_raw_parsed["text_block_text_part_is_text_list"].append(True)
        # done: add values to textGroupRawParsed.text_block_text_part_list



        # Read joined translations
        # print(f"reading {joined_translations_path}")
        with open(joined_translations_path) as f:
            joined_translations_text_raw = f.read()

        # Read splitted translations
        # print(f"reading {splitted_translations_path}")
        with open(splitted_translations_path) as f:
            splitted_translations_text_raw = f.read()

        # cleanup translation text
        def cleanup_translation(text):
            #global remove_regex_char_class
            # remove unwanted characters
            text = re.sub(rf'[{remove_regex_char_class}]', '', text)
            # Fix double quotes
            text = re.sub(r'[\u201c\u201d\u201e\u2033\u02dd\u030b\u030e\u05f4\u3003]', '"', text)
            # Fix single quotes
            text = re.sub(r'[\u2018\u2019\u02b9\u02bc\u02c8\u0301\u030d\u05f3\u2032]', "'", text)
            # Move comma out of quotes
            text = text.replace(',"', '",') # FIXME? re.sub
            # Replace "asdf..." with "asdf ..."
            text = re.sub(r'([a-z])\.\.\.(\b|$)', r'\1 ...', text)
            return text

        # Cleanup joined translations
        joined_translations_text = cleanup_translation(joined_translations_text_raw)

        # Cleanup splitted translations
        splitted_translations_text = cleanup_translation(splitted_translations_text_raw)

        # Combine content of "joined" and structure of "splitted" translations
        # Execute git diff command
        def exec_process(args, options={}):
            kwargs = dict(
                encoding="utf8",
                capture_output=True,
            )
            if options.get("allow_non_zero_status", False) == False:
                kwargs["check"] = True
            proc = subprocess.run(args, **kwargs)
            return proc
            # exec_options = {
            #     "encoding": "utf8",
            #     "maxBuffer": 100*1024*1024, # 100 MiB
            #     "windowsHide": True,
            #     **options
            # }
            # proc = child_process.spawnSync(args[0], args[1:], exec_options)
            # if not options.get("allow_non_zero_status", False):
            #     if proc.status != 0:
            #         raise ValueError(f"Command {args[0]} failed with status {proc.status}")
            # if not options.get("allow_error", False):
            #     if proc.error:
            #         raise ValueError(f"Command {args[0]} failed with error {proc.error}")
            # return proc

        # Get system user ID
        #system_user_id = exec_process(["id", "-u"]).stdout.strip()
        system_user_id = os.getuid()

        # Define temporary directory path
        tempdir_path = f"/run/user/{system_user_id}"

        # Define temporary file paths for joined and splitted translations
        joined_translations_text_temp_path = f"{tempdir_path}/translate-js-translation-joined.txt"
        splitted_translations_text_temp_path = f"{tempdir_path}/translate-js-translation-splitted.txt"

        # Write joined translations to temporary file
        write_file(joined_translations_text_temp_path, joined_translations_text)

        # Write splitted translations to temporary file
        write_file(splitted_translations_text_temp_path, splitted_translations_text)

        # Define arguments for git diff command
        git_diff_args = [
            "git", "diff",
            "--no-index", # compare files outside a git repo
            "--word-diff=color", # produce a fine-grained diff
            "--word-diff-regex=.", # character diff: compare every character, also whitespace
        ]





        # Define arguments for git diff command
        git_diff_joined_splitted_args = [
            *git_diff_args,
            joined_translations_text_temp_path,
            splitted_translations_text_temp_path,
        ]

        # Define options for git diff command
        git_diff_options = {
            "allow_non_zero_status": True,
        }

        # Execute git diff command
        diff_joined_splitted_translations_text = exec_process(git_diff_joined_splitted_args, git_diff_options).stdout
        diff_body_start_pos = 0

        # Find the start position of the diff body
        for i in range(5):
            diff_body_start_pos = diff_joined_splitted_translations_text.find("\n", diff_body_start_pos + 1)

        diff_body_start_pos += 1

        # Remove ANSI escape codes and unwanted characters from the diff output
        combined_joined_splitted_translations_text = re.sub(r'\x1b\[32m.*?\x1b\[m', '', diff_joined_splitted_translations_text[diff_body_start_pos:])
        combined_joined_splitted_translations_text = re.sub(r'\x1b\[[0-9;:]*[a-zA-Z]', '', combined_joined_splitted_translations_text)

        # Define a flag for debugging the other diff
        debug_also_do_the_other_diff = False

        # Perform the other diff if debugging is enabled
        if debug_also_do_the_other_diff:
            git_diff_splitted_joined_args = [
                *git_diff_args,
                splitted_translations_text_temp_path,
                joined_translations_text_temp_path,
            ]
            diff_splitted_joined_translations_text = exec_process(git_diff_splitted_joined_args, git_diff_options).stdout
            diff_body_start_pos = 0

            for i in range(5):
                diff_body_start_pos = diff_splitted_joined_translations_text.find("\n", diff_body_start_pos + 1)

            diff_body_start_pos += 1

            combined_splitted_joined_translations_text = re.sub(r'\x1b\[31m.*?\x1b\[m', '', diff_splitted_joined_translations_text[diff_body_start_pos:])
            combined_splitted_joined_translations_text = re.sub(r'\x1b\[[0-9;:]*[a-zA-Z]', '', combined_splitted_joined_translations_text)

            # Write temporary files for debugging
            diff_splitted_joined_translations_text_temp_path = f"{tempdir_path}/translate-js-translation-diff-splitted-joined.txt"
            combined_splitted_joined_translations_text_temp_path = f"{tempdir_path}/translate-js-translation-combined-splitted-joined.txt"

            print(f"writing {diff_splitted_joined_translations_text_temp_path}")
            write_file(diff_splitted_joined_translations_text_temp_path, diff_splitted_joined_translations_text)

            print(f"writing {combined_splitted_joined_translations_text_temp_path}")
            write_file(combined_splitted_joined_translations_text_temp_path, combined_splitted_joined_translations_text)

        # Define a flag for debugging the diff
        debug_diff = False

        # Clean up temporary files if debugging is disabled
        if not debug_diff:
            # Remove temporary files
            os.unlink(splitted_translations_text_temp_path)
            os.unlink(joined_translations_text_temp_path)
        else:
            # Keep temporary files
            print(f"keeping {splitted_translations_text_temp_path}")
            print(f"keeping {joined_translations_text_temp_path}")

            # Write more temporary files for debugging
            diff_joined_splitted_translations_text_temp_path = f"{tempdir_path}/translate-js-translation-diff-joined-splitted.txt"
            combined_joined_splitted_translations_text_temp_path = f"{tempdir_path}/translate-js-translation-combined-joined-splitted.txt"

            print(f"writing {diff_joined_splitted_translations_text_temp_path}")
            write_file(diff_joined_splitted_translations_text_temp_path, diff_joined_splitted_translations_text)

            print(f"writing {combined_joined_splitted_translations_text_temp_path}")
            write_file(combined_joined_splitted_translations_text_temp_path, combined_joined_splitted_translations_text)

        # Split the splitted translations into a list
        splitted_translations_list = splitted_translations_text.strip().split("\n")

        # TODO rename to joined_translations_list
        # Split the combined joined-splitted translations into a list
        combined_joined_splitted_translations_list = combined_joined_splitted_translations_text.strip().split("\n")

        last_splitted_translation_idx = -1

        # TODO are these "lines" or "blocks"?
        text_group_raw_parsed_idx = text_group_raw_parsed_idx_last

        # note: textGroupRawParsedIdxLast + 1 != textGroupRawParsedList.length
        # note: text_group_raw_parsed_idx_last + 1 != len(text_group_raw_parsed_list)
        # ... because new values were added in the "add values to textGroupRawParsedList" loop
        # we could also save textGroupRawParsedIdxLast before the "add values to textGroupRawParsedList" loop

        text_group_raw_parsed_is_first = True
        text_block_text_part_idx = 0

        # TODO line 3030:
        if debug_text_group_raw_parser:
            print(f"line 3250: textGroupRawParsedIdxLast {text_group_raw_parsed_idx_last}")

        # loop text parts: add aligned translations to textGroupRawParsedList
        # for (textGroupRawParsedIdx = textGroupRawParsedIdxLast; textGroupRawParsedIdx < textGroupRawParsedList.length; textGroupRawParsedIdx++) {
        while text_group_raw_parsed_idx < len(text_group_raw_parsed_list):

            if debug_text_group_raw_parser:
                print(f"line 3250: textGroupRawParsedIdx {text_group_raw_parsed_idx}")

            if text_group_raw_parsed_is_first:
                # continue
                if debug_alignment:
                    print(f"line 3260: textBlockTextPartIdxNext {text_block_text_part_idx_next} -> {text_block_text_part_idx_next_last}")
                text_block_text_part_idx_next = text_block_text_part_idx_next_last
                text_group_raw_parsed_is_first = False
            else:
                # reset
                if debug_alignment:
                    print(f"line 3260: textBlockTextPartIdxNext {text_block_text_part_idx_next} -> 0")
                text_block_text_part_idx_next = 0

            if debug_alignment:
                # console.log(`translatedFileId ${String(translatedFileId).padStart(5)}   textGroupRawParsedIdx ${String(textGroupRawParsedIdx).padStart(5)}`);
                print(f"translatedFileId {translated_file_id:5d}   textGroupRawParsedIdx {text_group_raw_parsed_idx:5d}")

            text_group_raw_parsed = text_group_raw_parsed_list[text_group_raw_parsed_idx]
            text_block_text_part_list = text_group_raw_parsed['text_block_text_part_list']
            text_block_text_part_is_text_list = text_group_raw_parsed['text_block_text_part_is_text_list']
            stop_loop_source_text_parts_loop = False

            # parent loop
            if debug_alignment:
                print("line 3030: translatedFileId", translated_file_id)

            # FIXME text_block_text_part_list is too long. 299 versus 3

            # FIXME textGroupRawParsedIdx should be 1, is 0

            # FIXME
            # py: a=0 b=4 c=13 d=158 sourceTextLine + splittedTranslationLine = "\"beautiful women seducing pious men\"." + "„Schöne Frauen verführen fromme Männer."
            # js: a=0 b=4 c=13 d=158 sourceTextLine + splittedTranslationLine = "\"beautiful women seducing pious men\"." + "„Schöne Frauen verführen fromme Männer\"."
            # py should not remove the double quote # FIXME def cleanup_translation
            # js should replace „ with double quote
            # py: a=0 b=4 c=7 d=155 sourceTextLine + splittedTranslationLine = "literally \"little maiden\"," + "wörtlich „kleines Mädchen,"
            # js: a=0 b=4 c=7 d=155 sourceTextLine + splittedTranslationLine = "literally \"little maiden\"," + "wörtlich „kleines Mädchen\","

            if debug_alignment:
                # FIXME
                # py: line 3030: looping textBlockTextPartIdx from 15 to 16
                # js: line 3030: looping textBlockTextPartIdx from 16 to 16
                print("line 3030: looping textBlockTextPartIdx from", text_block_text_part_idx_next, "to", len(text_block_text_part_list) - 1)

            if debug_alignment:
                print(f"loop from next ...")

            # loop text parts of this text block from next
            for text_block_text_part_idx in range(text_block_text_part_idx_next, len(text_block_text_part_list)):

                if debug_alignment:
                    # console.log(`translatedFileId ${String(translatedFileId).padStart(5)}   textGroupRawParsedIdx ${String(textGroupRawParsedIdx).padStart(5)}   textBlockTextPartIdx ${String(textBlockTextPartIdx).padStart(5)}`);
                    print(f"loop from next: translatedFileId {translated_file_id:5d}   textGroupRawParsedIdx {text_group_raw_parsed_idx:5d}   textBlockTextPartIdx {text_block_text_part_idx:5d}")

                # const textBlockTextPart = textBlockTextPartList[textBlockTextPartIdx];
                text_block_text_part = text_block_text_part_list[text_block_text_part_idx]

                text_block_text_part_is_text = text_block_text_part_is_text_list[text_block_text_part_idx]

                if not text_block_text_part_is_text:
                    whitespace_part_content = text_block_text_part
                    # read from text group raw parsed translations
                    for translation_line_list in text_group_raw_parsed["translations"].values():
                        # TODO translation_line_list = RandomWriteList()
                        translation_line_list[text_block_text_part_idx] = whitespace_part_content
                    continue

                # TODO rename sourceTextLine to textBlockTextPart
                # const sourceTextLine = textBlockTextPart;

                # TODO rename source_text_line to text_block_text_part
                #source_text_line = text_block_text_part.strip() # why strip?
                source_text_line = text_block_text_part

                translated_text_line_splitted = None
                translated_text_line_combined_joined_splitted = None

                if debug_alignment:
                    print(f"a={translated_file_id} b={text_group_raw_parsed_idx} c={text_block_text_part_idx} textBlockTextPart {json_dumps(text_block_text_part)}")

                # find translated text in splitted_translations_list

                # find "splitted" translation of this source text part

                #print("source_text_line", repr(source_text_line))

                splitted_translation_idx = last_splitted_translation_idx + 1

                # loop lines of the "splitted" translations
                while splitted_translation_idx < len(splitted_translations_list):

                    # this is always just one line (or less)
                    splitted_translation_line = splitted_translations_list[splitted_translation_idx]

                    if debug_alignment:
                        print(f"a={translated_file_id} b={text_group_raw_parsed_idx} c={text_block_text_part_idx} d={splitted_translation_idx} sourceTextLine + splittedTranslationLine =", json_dumps(source_text_line), "+", json_dumps(splitted_translation_line))

                    # start

                    # source_text_line 'who are my friends,'
                    # splitted_translation_line 'Wer sind meine Freunde,'

                    # source_text_line 'team composition,'
                    # splitted_translation_line 'Teamzusammensetzung,'

                    # source_text_line 'matchmaking,'
                    # splitted_translation_line 'Partnervermittlung,'

                    # source_text_line 'offline matchmaking,'
                    # splitted_translation_line 'Offline-Matchmaking,'

                    # ...

                    # source_text_line 'both are right,'
                    # splitted_translation_line 'beide haben recht,'

                    # last ok

                    # source_text_line ''
                    # splitted_translation_line '.'



                    # first fail

                    # source_text_line starts looping from start
                    # splitted_translation_line contnues looping

                    # source_text_line 'who are my friends,'
                    # splitted_translation_line '.'

                    # source_text_line 'team composition,'
                    # splitted_translation_line '(starke Meinungen),'

                    # source_text_line 'matchmaking,'
                    # splitted_translation_line '(„Sie haben sich vertippt!)'

                    # source_text_line 'offline matchmaking,'
                    # splitted_translation_line 'Pallas:'

                    # source_text_line 'interpersonal compatibility,'
                    # splitted_translation_line 'Name der griechischen Göttin,'



                    # source is empty line
                    # translation is not empty line
                    if source_text_line.strip() == "" and splitted_translation_line.strip() != "":
                        # copy whitespace from source
                        translated_text_line_splitted = source_text_line
                        translated_text_line_combined_joined_splitted = source_text_line.strip()
                        # dont use splittedTranslationLine
                        # dont update lastSplittedTranslationIdx
                        break

                    # source is "."
                    # translation is not "."
                    if source_text_line == "." and not splitted_translation_line.strip() == ".":
                        # copy "." from source
                        translated_text_line_splitted = source_text_line
                        translated_text_line_combined_joined_splitted = source_text_line.strip()
                        # dont use splittedTranslationLine
                        # dont update lastSplittedTranslationIdx
                        break

                    # source is not "."
                    # translation is "."
                    if source_text_line != "." and splitted_translation_line.strip() == ".":
                        # ignore this translation
                        splitted_translation_idx += 1
                        continue

                    translated_text_line_splitted = splitted_translation_line

                    if combined_joined_splitted_translations_list[splitted_translation_idx] == None:
                        print(f"warning: missing combined translation for {source_lang}-{target_lang}-{str(translated_file_id).zfill(3)}:{splitted_translation_idx}")

                    translated_text_line_combined_joined_splitted = (combined_joined_splitted_translations_list[splitted_translation_idx] or "").strip()

                    last_splitted_translation_idx = splitted_translation_idx
                    break
                # done: loop lines of the "splitted" translations

                if debug_alignment:
                    print(f"translatedFileId {translated_file_id:5d}   textGroupRawParsedIdx {text_group_raw_parsed_idx:5d}   textBlockTextPartIdx {text_block_text_part_idx:5d}   splittedTranslationIdx {splitted_translation_idx:5d}")

                if False and source_text_line == "extended families,":
                    raise "TODO"

                if translated_text_line_splitted == None:
                    #for idx, val in enumerate(splitted_translations_list):
                    for idx, val in enumerate(splitted_translations_list[0:20]):
                        print(f"splitted_translations_list[{idx}] = {repr(val)}")
                    raise ValueError(f'not found "splitted" translation of source_text_line: {repr(source_text_line)}')

                if translated_text_line_combined_joined_splitted == None:
                    raise ValueError(f'not found "combined" translation of source_text_line: {repr(source_text_line)}')

                # write to text group raw parsed translations
                #print('text_group_raw_parsed["translations"]', repr(text_group_raw_parsed["translations"])[0:200] + " ...")
                text_group_raw_parsed["translations"]["splittedTranslationLineList"][text_block_text_part_idx] = translated_text_line_splitted
                text_group_raw_parsed["translations"]["joinedTranslationLineList"][text_block_text_part_idx] = translated_text_line_combined_joined_splitted

            # done: loop text parts of this text block from next

            if stop_loop_source_text_parts_loop:
                break

            text_group_raw_parsed_idx += 1

        # done: loop text parts: add aligned translations to textGroupRawParsedList

        if debug_alignment:
            print(f"line 3500: textGroupRawParsedIdx {text_group_raw_parsed_idx}   textGroupRawParsedIdxLast {text_group_raw_parsed_idx_last}")

        # undo "textGroupRawParsedIdx++" in the previous for loop
        text_group_raw_parsed_idx_last = text_group_raw_parsed_idx - 1

        if debug_alignment:
            print(f"line 3505: textGroupRawParsedIdx {text_group_raw_parsed_idx}   textGroupRawParsedIdxLast {text_group_raw_parsed_idx_last}")

        if debug_alignment:
            print(f"line 3510: textBlockTextPartIdxNextLast {text_block_text_part_idx_next_last} -> {text_block_text_part_idx + 1}")

        # FIXME text_block_text_part_idx is 1 too small
        #text_block_text_part_idx_next_last = text_block_text_part_idx
        # +1:
        # in javascript, textBlockTextPartIdx was incremented after the last iteration
        # of "loop text parts of this text block from next"
        # textBlockTextPartIdx++
        # in python, text_block_text_part_idx was *not* incremented after the last iteration
        text_block_text_part_idx_next_last = text_block_text_part_idx + 1

    # done: loop input files: add source and translated text parts to textGroupRawParsed

    print("populating textGroupRawParsedList done")



    print("autofixing and autosolving translations ...")

    # TODO move out
    def autofix_translations(source_text, translated_text_list, target_lang):
        if target_lang == "en":
            # Define a mapping of contractions to their expanded forms
            contraction_mapping = {
                r"\b(i|you|he|she|it|we|they)'ll\b": r"\1 will",
                r"\b(w)on't\b": r"\1ill not",
                r"\b(c)an't\b": r"\1an not",
                r"\b(do|does|did|is|was|were|should|could|have|would|are)n't\b": r"\1 not",
                r"\b(i|you|they|we)'ve\b": r"\1 have",
                r"\b(i|you|he|she|it|we|they)'d\b": r"\1 would",
                r"\b(who|that|there|what|it)'s\b": r"\1 is",
                r"\b(i)'m\b": r"\1 am",
                r"\b(you|we|they)'re\b": r"\1 are",
                r"\b(he|she|it)'s\b": r"\1 is",
                r"\b(let)'s\b": r"\1 us"
                # Add more contractions as needed
            }

            # Iterate through each translated text and apply fixes
            for idx, translated_text in enumerate(translated_text_list):
                for pattern, replacement in contraction_mapping.items():
                    translated_text_list[idx] = re.sub(pattern, replacement, translated_text, flags=re.IGNORECASE)

        return translated_text_list
    # done: def autofix_translations



    # autosolve translations
    def autosolve_translations(source_text, translated_text_list):
        if len(translated_text_list) <= 1:
            # 0 or 1 translation. no translations to compare
            if debug_alignment:
                print("3670 autosolveTranslations 1")
            return translated_text_list

        # source and translations are equal
        for translated_text in translated_text_list:
            if translated_text == source_text:
                if debug_alignment:
                    print("3670 autosolveTranslations 2")
                return [translated_text]

        # all translations are equal
        if all(translated_text == translated_text_list[0] for translated_text in translated_text_list):
            if debug_alignment:
                print("3670 autosolveTranslations 3")
            return [translated_text_list[0]]

        if debug_alignment:
            print("3670 autosolveTranslations 4")

        # Check for trivial differences
        end_punctuation_regex = r'[.,?!" ]+$'
        only_punctuation_regex = r'^[.,?!" ]+$'

        # get line end punctuation
        def get_line_end_punctuation(line):
            match = re.search(end_punctuation_regex, line)
            return match.group(0) if match else None

        source_text_end_punctuation = get_line_end_punctuation(source_text)

        if debug_alignment:
            print(f"3710 autosolveTranslations 4 sourceTextEndPunctuation {json_dumps(source_text_end_punctuation)}")

        if source_text_end_punctuation:

            # source line ends with punctuation

            # prefer translations that also end with the same punctuation
            # but otherwise have the same prefix

            # example:
            # de-en-000:70:
            #   s: Nur wenige Weltbilder geben eine Antwort,
            #   t: Only a few worldviews provide an answer
            #   t: Only a few worldviews provide an answer,

            filtered_translated_text_list = translated_text_list[:]

            for translated_text in translated_text_list:

                if not translated_text.endswith(source_text_end_punctuation):
                    if debug_alignment:
                        print("3670 autosolveTranslations 4 1")
                    continue

                # translatedText has same end punctuation as sourceText
                # remove other translated texts that only differ in end punctuation

                translated_text_before_end_punctuation = translated_text[:(-1 * len(source_text_end_punctuation))]

                if debug_alignment:
                    print(f"3670 autosolveTranslations 4 1 translatedTextBeforeEndPunctuation {json_dumps(translated_text_before_end_punctuation)}")

                def filter_translated_text(translated_text_2):
                    if (
                        not translated_text_2.startswith(translated_text_before_end_punctuation)
                        or
                        translated_text_2 == translated_text
                    ):
                        if debug_alignment:
                            print("3670 autosolveTranslations 4 2")
                        return True # keep translation

                    #   translatedText2 has same prefix as translatedText, but a different suffix
                    suffix = translated_text_2[len(translated_text_before_end_punctuation):]
                    if (
                        suffix == "" or
                        re.match(only_punctuation_regex, suffix)
                    ):
                        # suffix has no words
                        if debug_alignment:
                            print("3670 autosolveTranslations 4 3")
                        return False # remove translation
                    # suffix has words
                    if debug_alignment:
                        print("3670 autosolveTranslations 4 4")
                    return True # keep translation

                filtered_translated_text_list = list(filter(
                    filter_translated_text,
                    filtered_translated_text_list
                ))
            translated_text_list = filtered_translated_text_list

            if debug_alignment:
                print("3670 autosolveTranslations 5")

            # add missing end punctuation to translated texts
            # de-en-000:89:
            #   s: Wie müssen wir verschiedene Menschen verbinden,
            #   t: How do we need to connect different people
            #   t: How do we have to connect different people,

            def map_translated_text(translated_text):
                if translated_text.endswith(source_text_end_punctuation):
                    return translated_text # no change
                suffix = get_line_end_punctuation(translated_text)
                if suffix == None:
                    # translated text does NOT end with punctuation
                    # add end punctuation
                    return translated_text + source_text_end_punctuation
                return translated_text # no change

            translated_text_list = list(map(
                map_translated_text,
                translated_text_list
            ))

        else:

            if debug_alignment:
                print("3670 autosolveTranslations 6")

            # source line does not end with punctuation

            # sourceTextEndPunctuation == undefined
            # source line does NOT end with punctuation

            # prefer translations that also do NOT end with punctuation
            # but otherwise have the same prefix

            # example:
            # de-en-000:27:
            #   s: Wer sind meine Freunde
            #   t: Who are my friends
            #   t: Who are my friends?

            filtered_translated_text_list = translated_text_list[:]
            for translated_text in translated_text_list:
                translated_text_end_punctuation = get_line_end_punctuation(translated_text)
                if translated_text_end_punctuation != None:
                    if debug_alignment:
                        print(f"3670 autosolveTranslations 6 1 translatedTextEndPunctuation {json_dumps(translated_text_end_punctuation)}")
                    continue
                if debug_alignment:
                    print(f"3670 autosolveTranslations 6 1 translatedText {json_dumps(translated_text)}")
                # translated_text_end_punctuation == None
                # translatedText also has NO end punctuation
                # remove other translated texts that only differ in end punctuation
                def filter_translated_text(translated_text_2):
                    if debug_alignment:
                        print(f"3670 autosolveTranslations 6 1.5 translatedText2 {json_dumps(translated_text_2)}")
                    if translated_text_2 == translated_text:
                        if debug_alignment:
                            print("3670 autosolveTranslations 6 2")
                        return True # keep translation
                    if translated_text_2.startswith(translated_text):
                        # translatedText2 has same prefix as translatedText, but a different suffix
                        if debug_alignment:
                            print("3670 autosolveTranslations 6 3")
                        return False # remove translation
                    if debug_alignment:
                        print("3670 autosolveTranslations 6 4")
                    return True # keep translation
                # force eval of filter here
                # to get the same output as the js version
                filtered_translated_text_list = list(filter(
                    filter_translated_text,
                    filtered_translated_text_list
                ))
            translated_text_list = filtered_translated_text_list

        return translated_text_list
    # done: def autosolve_translations



    text_group_raw_parsed_last = None  # debug

    # loop text blocks: autofix and autosolve translations in textGroupRawParsed
    for text_block_idx, text_group_raw_parsed in enumerate(text_group_raw_parsed_list):
        if debug_alignment:
            print(f"textBlockIdx {str(text_block_idx).rjust(5)}")
        text_block_text_part_list = text_group_raw_parsed["text_block_text_part_list"]

        if debug_alignment:
            print(f"loop from first ...")

        # loop text parts of this text block from first
        for text_block_text_part_idx, text_block_text_part in enumerate(text_block_text_part_list):

            if debug_alignment:
                print(f"loop from first: textBlockIdx {str(text_block_idx).rjust(5)}   textBlockTextPartIdx {str(text_block_text_part_idx).rjust(5)}   (translatedFileId {str(text_group_raw_parsed['translated_file_id']).rjust(5)})")

            source_text_line = text_block_text_part.strip()

            source_text_line_trimmed = text_block_text_part.strip()

            if debug_alignment:
                print(f"3550 sourceTextLineTrimmed {json_dumps(source_text_line_trimmed)}")

            if (
                # this part is whitespace only
                not text_group_raw_parsed["text_block_text_part_is_text_list"][text_block_text_part_idx] or
                # this part is punctuation only
                source_text_line in [".", ",", ":"]
                # TODO exclude more?
            ):
                continue

            # read from text group raw parsed translations
            translated_text_line_splitted = text_group_raw_parsed["translations"]["splittedTranslationLineList"][text_block_text_part_idx]
            translated_text_line_combined_joined_splitted = text_group_raw_parsed["translations"]["joinedTranslationLineList"][text_block_text_part_idx]

            # debug
            # if debug_alignment and text_group_raw_parsed["translatedFileId"] >= 82:
            #     print(f"textBlockIdx {text_block_idx}")
            #     print(text_group_raw_parsed)

            if translated_text_line_combined_joined_splitted is None:
                print(
                    f"Translated text line combined joined splitted is None. Block Idx: {text_block_idx}, Text Group Raw Parsed: {text_group_raw_parsed}, Text Block Text Part Idx: {text_block_text_part_idx}, Translated Text Line Combined Joined Splitted: {translated_text_line_combined_joined_splitted}, Translated Text Line Splitted: {translated_text_line_splitted}"
                )
                raise ValueError("Translated text line combined joined splitted is None")

            if translated_text_line_splitted is None:
                print(
                    f"Translated text line splitted is None. Block Idx: {text_block_idx}, Text Group Raw Parsed: {text_group_raw_parsed}, Text Block Text Part Idx: {text_block_text_part_idx}, Translated Text Line Combined Joined Splitted: {translated_text_line_combined_joined_splitted}, Translated Text Line Splitted: {translated_text_line_splitted}"
                )
                raise ValueError("Translated text line splitted is None")

            #translated_text_part_list = []

            translated_text_line_list = [translated_text_line_combined_joined_splitted, translated_text_line_splitted]

            if debug_alignment:
                print("3840 sourceTextLineTrimmed", json_dumps(source_text_line_trimmed))
                print("3840 translatedTextLineList", json_dumps(translated_text_line_list))

            # first autofix, then autosolve
            # because autofix can produce more identical translations
            # which are then reduced by autosolve

            translated_text_line_list = autofix_translations(source_text_line_trimmed, translated_text_line_list, target_lang)

            if debug_alignment:
                print("3845 translatedTextLineList", json_dumps(translated_text_line_list))

            # FIXME returns empty
            translated_text_line_list = autosolve_translations(source_text_line_trimmed, translated_text_line_list)

            if debug_alignment:
                print("3850 translatedTextLineList", json_dumps(translated_text_line_list))

            # write to text group raw parsed translations
            # Write back to textGroupRawParsed.translations
            # First translation in translatedTextLineList is the "joined" translation
            # textGroupRawParsed.translations.joinedTranslationLineList[textBlockTextPartIdx] = (
            text_group_raw_parsed["translations"]["joinedTranslationLineList"][text_block_text_part_idx] = (
                translated_text_line_list[0]
            )
            # Second translation in translatedTextLineList is the "splitted" translation
            # If it was removed by autosolve, then just copy the "joined" translation
            # textGroupRawParsed.translations.splittedTranslationLineList[textBlockTextPartIdx] = (
            text_group_raw_parsed["translations"]["splittedTranslationLineList"][text_block_text_part_idx] = (
                # FIXME index error: translated_text_line_list[1]
                #translated_text_line_list[1] or translated_text_line_list[0]
                translated_text_line_list[1] if len(translated_text_line_list) > 1 else translated_text_line_list[0]
            )

            # textGroupRawParsedLast = textGroupRawParsed;

        # done: loop text parts of this text block from first

    # done: loop text blocks: autofix and autosolve translations in textGroupRawParsed



    print("autofixing and autosolving translations done")
    # TODO use translatedTextLineList



    # Debug: Write textGroupRawParsedList to a JSON file
    text_group_raw_parsed_list_path = "debug-textGroupRawParsedList.json"
    print(f"writing {text_group_raw_parsed_list_path}")
    with open(text_group_raw_parsed_list_path, "w") as json_file:
        json.dump(text_group_raw_parsed_list, json_file, indent=2, ensure_ascii=False)

    # Transform textGroupRawParsedList to an object using sourceTextBlockHash as key
    # Assuming sourceTextBlockHash is available in textGroupRawParsedList

    text_group_raw_parsed_dict = {}
    for text_group_raw_parsed in text_group_raw_parsed_list:
        text_group_raw_parsed_dict[text_group_raw_parsed["source_text_block_hash"]] = text_group_raw_parsed

    # Main loop: textToTranslateList + htmlBetweenReplacementsList
    # Write HTML by looping through source text list and getting translations from translatedTextLineListByInputFileList

    # Debug: Compare translations in plain text format
    # Make something similar in HTML where we see vertical stacks of source text and translation candidates
    # Let's assume we have a function to generate HTML comparison

    # Assuming generate_html_comparison() is a function to generate HTML comparison
    # html_comparison = generate_html_comparison(source_text_list, translated_text_line_list_by_input_file_list)
    # translated_text += html_comparison.translated_text

    translated_html = io.StringIO()
    translated_splitted_html = io.StringIO()

    # Main loop to reconstruct HTML
    for text_to_translate_idx, text_to_translate_entry in enumerate(text_to_translate_list):
        html_before_text = html_between_replacements_list[text_to_translate_idx]
        translated_html.write(html_before_text)
        translated_splitted_html.write(html_before_text)

        _idx, source_hash, source_lang, source_text, todo_remove_end_of_sentence, todo_add_to_translations_database = text_to_translate_entry

        translated_text_block_text = None
        translated_splitted_text_block_text = None

        if source_hash == "":
            translated_text_block_text = ""

        if translated_text_block_text is None:
            # translation_key = f"{source_lang}:{target_lang}:{source_hash}"
            # translated_text_block_text = translations_database.get(translation_key, [])[1]
            joined_splitted = translations_db.get_target_text(
                source_lang,
                source_hash,
                target_lang,
                translator_name
            )
            if joined_splitted:
                #print("joined_splitted", repr(joined_splitted))
                joined_translation_block_text, splitted_translation_block_text = joined_splitted
                translated_text_block_text = joined_translation_block_text
                if joined_translation_block_text != splitted_translation_block_text:
                    translated_splitted_text_block_text = splitted_translation_block_text

        if translated_text_block_text is None:
            text_group_raw_parsed = next(
                (parsed_group for parsed_group in text_group_raw_parsed_list if parsed_group["source_text_block_hash"] == source_hash),
                None
            )
            if text_group_raw_parsed is None:
                print({
                    "text_to_translate_idx": text_to_translate_idx,
                    "source_hash": source_hash,
                    "source_lang": source_lang,
                    "source_text": source_text,
                    "todo_remove_end_of_sentence": todo_remove_end_of_sentence,
                    "todo_add_to_translations_database": todo_add_to_translations_database,
                })
                raise ValueError("TODO find translation in translated_text_line_list_by_input_file_list")

            # read from text group raw parsed translations
            joined_translation_block_text = "".join(text_group_raw_parsed["translations"]["joinedTranslationLineList"])
            splitted_translation_block_text = "".join(text_group_raw_parsed["translations"]["splittedTranslationLineList"])

            translations_db.add_target_text(
                source_lang,
                source_hash,
                target_lang,
                translator_name,
                joined_translation_block_text,
                splitted_translation_block_text
            )

            translated_text_block_text = joined_translation_block_text

            if joined_translation_block_text != splitted_translation_block_text:
                translated_splitted_text_block_text = splitted_translation_block_text

        if translated_text_block_text is None:
            print({
                "text_to_translate_idx": text_to_translate_idx,
                "source_hash": source_hash,
                "source_lang": source_lang,
                "source_text": source_text,
                "todo_remove_end_of_sentence": todo_remove_end_of_sentence,
                "todo_add_to_translations_database": todo_add_to_translations_database,
            })
            raise ValueError("FIXME missing translation for this text block")

        translated_html.write(translated_text_block_text)

        if translated_splitted_text_block_text is None:
            translated_splitted_html.write(translated_text_block_text)
        else:
            translated_splitted_html.write(translated_splitted_text_block_text)
    # done: Main loop to reconstruct HTML

    # Add last HTML chunk
    translated_html.write(html_between_replacements_list[-1])
    translated_splitted_html.write(html_between_replacements_list[-1])

    translated_html = translated_html.getvalue()
    translated_splitted_html = translated_splitted_html.getvalue()

    # Write to files
    print(f"writing {translated_html_path}")
    with open(translated_html_path, "w") as html_file:
        html_file.write(translated_html)

    print(f"writing {translated_splitted_html_path}")
    with open(translated_splitted_html_path, "w") as splitted_html_file:
        splitted_html_file.write(translated_splitted_html)

    return input_path_frozen



# TODO remove? python version is using sqlite database

def parse_translations_database(translations_database, translations_database_text):

    def sha1sum(text):
        return 'sha1-' + hashlib.sha1(text.encode('utf-8')).hexdigest()

    def replace_callback(match):
        translation_key, source_text, translated_text = match.groups()
        source_lang, target_lang, source_hash = translation_key.split(":")
        source_hash_actual = sha1sum(source_text)
        if source_hash != source_hash_actual:
            print(f"error: parseTranslationsDatabase: sourceHash != sourceHashActual: {source_hash} != {source_hash_actual}: sourceText = {source_text[:100]} ...", file=sys.stderr)
            raise ValueError("fixme")
        translations_database[translation_key] = [source_text, translated_text]
        # source_text_hash_bytes = bytes.fromhex(source_hash)
        # target_text = translated_text
        # translations_db_set(source_lang, target_lang, source_text_hash_bytes, source_text, target_text)
        return ""

    translations_database_text = re.sub(
        r'\n<h2 id="[^"]+">([^<]+)<\/h2>\n<table style="width:100%"><tr>\n<td style="width:50%"><pre style="white-space:pre-wrap">\n(.*?)\n<\/pre><\/td>\n<td style="width:50%"><pre style="white-space:pre-wrap">\n(.*?)\n<\/pre><\/td>\n<\/tr><\/table>\n',
        replace_callback,
        translations_database_text,
        flags=re.s
    )

    if not translations_database_text.startswith('<h1>translations database'):
        print("warning: parseTranslationsDatabase did not parse all input. rest:", translations_database_text, file=sys.stderr)



async def translate_lang(input_path, target_lang, output_dir):

    print(f"reading {input_path}")
    with open(input_path, 'r') as file:
        input_html_bytes = file.read()
    input_html_hash = 'sha1-' + hashlib.sha1(input_html_bytes.encode('utf-8')).hexdigest()

    output_dir = os.path.join(os.path.dirname(input_path), output_dir)

    if input_path.endswith(input_html_hash):
        # input path is already frozen
        input_path_frozen = input_path
    else:
        input_path_frozen = output_dir + os.path.basename(input_path) + '.' + input_html_hash

    # TODO rename input_path_frozen to output_base
    output_base = input_path_frozen

    translate_url_list_path = output_base + f".translateUrlList-{target_lang}.json"
    print(f"reading {translate_url_list_path}")
    with open(translate_url_list_path, 'r') as file:
        translate_url_list = json.load(file)

    translate_url_list_filtered = []

    for translate_item in translate_url_list:

        # link_id:
        # 0000-joined
        # 0000-splitted
        # ...

        link_id, translate_url = translate_item

        translation_output_path = f"{output_base}.{link_id}.txt"

        if os.path.exists(translation_output_path):
            print(f"keeping output: {translation_output_path}")
            continue

        translate_url_list_filtered.append(translate_item)

    if len(translate_url_list_filtered) == 0:
        return input_path_frozen
    
    print("len(translate_url_list_filtered)", len(translate_url_list_filtered))
    
    raise "FIXME" # dont reach this

    translate_url_list = translate_url_list_filtered

    print("starting chromium")

    chrome_options = webdriver.ChromeOptions()

    async with webdriver.Chrome(options=chrome_options) as driver:

        print("starting chromium done")
        await driver.sleep(10)

        # on first visit, autosolve "Before you continue to Google" popup
        print("autosolving accept-terms popup")
        url = "https://translate.google.com/"
        await driver.get(url)
        # <span jsname="V67aGc" class="VfPpkd-vQzf8d">Accept all</span>
        accept_all = await driver.find_element(By.XPATH, "//span[text()='Accept all']")
        await accept_all.click()
        # wait for page load
        await driver.sleep(10)

        for translate_item in translate_url_list:

            # link_id:
            # 0000-joined
            # 0000-splitted
            # ...

            link_id, translate_url = translate_item

            translation_output_path = f"{output_base}.{link_id}.txt"

            if os.path.exists(translation_output_path):
                print(f"keeping output: {translation_output_path}")
                continue

            print(f"translating group {link_id}")

            await driver.get(translate_url)

            # wait for page load
            await driver.sleep(10)

            # override the "set clipboard" function
            print("overriding navigator.clipboard.writeText")
            await driver.execute_script(
                "navigator.clipboard.writeText = (text) => globalThis._clipboard = text;"
            )

            print(f"clicking copy translation")
            # click <button aria-label="Copy translation"
            # selenium_driverless.types.webelement.NoSuchElementException
            copy_translation = await driver.find_element(By.XPATH, "//button[@aria-label='Copy translation']", timeout=120)
            await copy_translation.click()

            # wait for clipboard
            await driver.sleep(5)

            print(f"getting clipboard")
            target_text = await driver.execute_script(
                "return globalThis._clipboard"
            )
            print("target_text", target_text[:50] + " ...")

            print(f"writing {translation_output_path}")
            with open(translation_output_path, "w") as f:
                f.write(target_text)

            # use ascii doublequotes
            # TODO use code from import_lang
            #clipboard = clipboard.replace('„', '"').replace('“', '"')

            # give translator some time to chill
            # avoid getting blocked by rate limiting
            await driver.sleep(10)

    return input_path_frozen



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
        return await import_lang(input_path, target_lang, output_dir, translations_path_list)

    input_path_frozen = await export_lang(input_path, target_lang, output_dir)

    input_path = input_path_frozen
    output_dir = ""

    await translate_lang(input_path, target_lang, output_dir)

    # .translation-en-de-0001-joined.txt
    # .translation-en-de-0001-splitted.txt
    # ...

    # TODO filter more? glob pattern may be too lax
    # see also translations_base_name_match

    # sorting is done by import_lang
    #translations_path_list = sorted(glob.glob(input_path_frozen + f".translation-*-*-*-*.txt"))

    translations_path_list = glob.glob(input_path_frozen + f".translation-*-*-*-*.txt")

    translations_path_list_len = len(translations_path_list)

    assert translations_path_list_len % 2 == 0, f"unexpected translations_path_list_len {translations_path_list_len}"

    await import_lang(input_path, target_lang, output_dir, translations_path_list)



if __name__ == "__main__":
    import asyncio
    asyncio.run(main())
