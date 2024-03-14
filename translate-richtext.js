#!/usr/bin/env node

// FIXME nodeTypeId is not stable

// https://github.com/tree-sitter/py-tree-sitter/issues/202
// py-tree-sitter is 10x slower than lezer-parser

//throw new Error("TODO update node ids of @lezer/html from version 1.3.6 to 1.3.9")

// based on src/alchi-book/scripts/translate.js

// TODO in exportLang, remove lang="en" from outputTemplateHtml
// when targetLang == "en"
// only keep <html lang="en">
// also remove (lang="en") from comments: <!--(lang="en") ... -->

// TODO add lang="de" to untranslated parts
// example:
//   <span class="note">predictions<span style="display:none">
//     TODO 16personalities macht Vorhersagen zur Kompatibilität
//   </span></span>
// the annotation was not translated
// it had no explicit lang="de" attribute
// but it inherited lang from <html lang="de">

// FIXME to get the "joined" translations
// we have to send full sentences to the translator
// so we cannot remove "already translated" parts of sentences
// example:
//   This is some sentence with <b>some already translated words</b>, you see?
// if the part "some already translated words" has already been translated
// and is already stored in the the translations database
// then we can only remove it from the source text for the "splitted" translation
// but not from the source text for the "joined" translation

/*
TODO remove empty <span> tags that were used only for lang="..."

<div lang="en" class="para">
  Fuck the system! <span lang="de">Aber diesmal richtig.</span>
</div>
*/

// FIXME keep lang="..." of notranslate tags if sourceLang != targetLang
/*
  <span lang="latin" class="notranslate">Si vis pacem, para bellum.</span>
  <span lang="fr" class="notranslate">Laisse faire, la nature.</span>
*/

// TODO update existing translated documents

// TODO render a side-by-side view of source and translated text
// with aligned text parts

// TODO add "translation based on ..." info to the output html
// something like
//   <meta name="translation-based-on-file-name" value="input.html" class="notranslate">
//   <meta name="translation-based-on-git-blob" value="6183d1520516dfeb3ec3c77ec8248a7599d3e67d" class="notranslate">
// then the original file can be produced with
//   git cat-file blob 6183d1520516dfeb3ec3c77ec8248a7599d3e67d

// TODO add "translated license" to non-english translations
// https://github.com/milahu/mit-license

// TODO autofix: "i.e." -> "in effect,"

// TODO autofix: "cannot" -> "can not"

// TODO test the "v2 beta" version of argos-translate
/*
cd ~/src/milahu/nur-packages
nix-build . -A python3Packages.argostranslate_2
PYTHONPATH=$PYTHONPATH:/nix/store/jinijfbh62d55bzzy9476wrgnglgr571-python3.10-argostranslate-2.alpha/lib/python3.10/site-packages
*/

// warning: this code is a horrible mess
// ideally i would do a rewrite from scratch
// but i dont have the time...



// write errors to stdout to keep stdout and stderr in sync
console.error = console.log;

const debugAlignment = false;

const translateComments = false;
const translateTitleAttr = false;
const translateMetaContent = true;

//const sleepBetweenTranslationRequests = 10 * 1000;


/*
// https://stackoverflow.com/a/39914235/10440128
function sleep(ms) {
    return new Promise(resolve => setTimeout(resolve, ms));
}
*/


// see also
// https://webapps.stackexchange.com/questions/52668/prohibit-the-translation-of-pieces-of-text-in-google-translate/154694#154694
// https://github.com/ssut/py-googletrans/issues/99#issuecomment-848714972

// alternatives
// https://github.com/Frully/html-google-translate
//   based on https://github.com/Frully/google-translate-open-api
//     Free and unlimited
//     (translate.google.com uses a token to authorize the requests.
//     If you are not Google, you do not have this token
//     and will have to pay $20 per 1 million characters of text)

// TODO translate svg files

// TODO refactor src/pages/*.html to use <lang.de> instead of <de> etc. -> make tags unambiguous
// e.g. <tr> can be turkish or table row

// TODO avoid double inserts

// TODO verify: all text-fragments are inserted

// TODO auto-detect sourceLangList from files in src/pages/*.html

// TODO post-process old and manual translations
// -> add/update rev="en#xxxxxxxx" (revision ID) to keep translations in sync
// use different encoding than base64? base32 or base16 (hex) -> better for filenames
// -> easier to build a content-addressable store to cache old versions
// con: text fragments are small -> use one large database file, e.g. jsonlines format
// collision safety? git uses short IDs of only 7 chars in base16

// FIXME [-{_>] can be translated to [-{_}]
// example: translations-store/de-en-sha1-7f77643ee85951e4b66d0b9656afaa78061d9898.translation.txt.broken-code
// input: input.html.sha1-6b994e5f12c80d8ffcb4a9722cd51460a39a1f96.groups.json
// for now, im manually fixing the translation.txt file
// based on the sequence of codes in the input files
// TODO maybe automate this fixing
// see "wild guess: the translator translated our code"
// TODO show context of the broken code: source versus translation
// TODO use unicode symbols instead of ascii codes?
// these should be non-text symbols, so they are not translated

// FIXME [_-_{] can be translated to [_-_-]
// translations-store/de-en-sha1-5d2fca6fd68c766edca573ca3abedcc6e23abab6.translation.txt.broken-code

// FIXME [</^<] can be translated to [</^ ^<]
// translations-store/de-en-sha1-01144fcc0bfa61f74471d152eed40852e072c780.translation.txt.broken-code

// FIXME ['-'^}] can be translated to ['-'^] ... }]
// es sind ja im Internet sämtliche ['-'^/]  ['-'^_] Lehrpläne ['-'^{] ['-'^}] zugänglich
// there are all ['-'^/] ['-'^_] curricula ['-'^{] ['-'^] on the Internet }] accessible

// FIXME ['-</}] can be translated to ['-</{}]
// Bevor sie mich holten, wusste ich, sie würden kommen, ['-</}] jetzt sitze ich im Knast und werd jeden Tag vernommen.
// Before they took me, I knew they were coming, ['-</{}] now I'm in jail and being questioned every day.

// 12 safe symbols: []^'*-/_{}<>
// ascii codes
/*
const codeNumKey = "^'*-/_{}<>"; // 10 digits -> base 10 code
const codeNumRegexCharClass = "\\^'*-/_{}<>"; // escape ^ for regex character class
*/
// unicode codes
// also unicode codes are broken by google translate
// [☢☥] is replaced with [☢☤]
// error: duplicate replaceId 8740
// { _replacement: '[☢☤]', idxStr: '☢☤', replaceId: 8740, rest: '' }
// couldn't remember anything at all, [☢☡] except for the [☢☢] [☢☣] veracity of his claims [☢☤] [☢☤] [ ☢☥] . [☢☦] [☢☧] I stood there rigid many a time. [☢☨] [☢☩] You didn't know what to admire more, [☢☪] her eloquence or her art of [☢☫] [☢☬] lying [☢☭] [☢☮] .
// bewiesene [☢☢]  [☢☣] Richtigkeit seiner Behauptungen [☢☤]  [☢☥] . [☢☦]  [☢☧] Ich stand manches Mal starr da. [☢☨]  [☢☩] Man wußte nicht, was man mehr best
// TODO use single char unicode codes
// -> no, is also broken

// also broken: verbose ascii code `ref${num}`;
// [\"ref2663\"] also wenn sein Subtyp stabilere Bindungen zum gleichen Geschlecht hat, [\"ref2664\"] dann hat dieser Mensch auch \"heterosexuelle\" Bindungen (zum anderen Geschlecht), [\"ref2665\"] aber diese Bindungen sind eher labil (weniger stabil, seltener).
// ["ref2663"] i.e. if his subtype has more stable ties to the same sex, ["ref2664"] then this person also has "heterosexual" ties (to the opposite sex), ["ref2662"] "ref2665"] but these bonds are rather unstable (less stable, less common). ["ref2666"]



// translator can remove sentences
// missing refs: ref8383 ref8384 ref8385
// removed sentence: Die Missgeburt vom Jugendamt wird sich eine Kugel fangen
// but the translator works on this small text:
/*
Ich rasiere mein Äffchen und lass es anschaffen, [\"ref8380\"]
tret so lange auf dein Kopf, bis vier und drei acht machen. [\"ref8381\"]  [\"ref8382\"]
Die Missgeburt vom Jugendamt wird sich eine Kugel fangen [\"ref8383\"]  [\"ref8384\"] , [\"ref8385\"]
meine Eltern sind seit neun Jahren im Urlaub, Mann. [\"ref8386\"]
*/
/*
I'll shave my little monkey and have it done, ["ref8380"]
step on your head until four and three make eight.
My parents have been on vacation for nine years, man. ["ref8386"]
*/
// so... was the sentence removed because the translator is stupid or evil?



//const codeNumRegexCharClass = "\\u2600-\\u26FF";
// verbose ascii code `ref${num}`;
// "ref" as in "reference". this should look like a footnote-reference
const codeNumRegexCharClass = "0-9";

// FIXME translator removes unicode codes
// [⚪]  [⚫] Ob und wie die Diagonal-Paare funktionieren, [⚬] weiss ich noch nicht. Diagonal-Paare: MS-FL und FS-ML. [⚭]  [⚮]
// [⚪] [⚫] I don't yet know whether and how the diagonal pairs work. Diagonal pairs: MS-FL and FS-ML. [⚭] [⚮]
// warning: unsteady replaceIdRaw: 171 -> 173 = code: ⚫ -> ⚭
// -> [⚬] was removed, this is bad...
// we need codes that are ALWAYS preserved by the translator

// this looks better:
// [⚪]  [⚫]  ["ref6"] Ob ["ref7"] und ["ref8"] wie ["ref9"] die ["ref10"] Diagonal-Paare ["ref11"] funktionieren ["ref12"], ["ref1"] weiss ["ref2"] ich ["ref3"] noch ["ref4"] nicht ["ref5"]. ["ref13"] Diagonal-Paare ["ref14"]: MS-FL und FS-ML. ["ref15"] [⚭]  [⚮]
// [⚪] [⚫] ["ref6"] Whether ["ref7"] and ["ref8"] work like ["ref9"] the ["ref10"] diagonal pairs ["ref11"] ["ref12"], ["ref1"] don't know ["ref2"] I ["ref3"] nor ["ref4"] ["ref5"]. ["ref13"] Diagonal pairs ["ref14"]: MS-FL and FS-ML. ["ref15"] [⚭] [⚮]

const removeRegexCharClass = [
  '\u200B', // ZERO WIDTH SPACE from google https://stackoverflow.com/questions/36744793
].join('');

const artifactsRegexCharClass = removeRegexCharClass + [
  ' ', // space
  // this is valid source text: […] = [...]
  //'…', // 8230
].join('');

// "import" because this is used only in importLang
// where we have to deal with errors introduced by the translate service
const codeNumRegexCharClassImport = codeNumRegexCharClass + artifactsRegexCharClass;

// no. valid replacementId are all integers >= 0
// expected range: 9728 to 9983
/*
function isValidReplacementId(num) {
  return (9728 <= num && num <= 9983);
}
*/

// ascii codes
//const encodeNumTable = Object.fromEntries(codeNumKey.split('').map((c, i) => [i, c]));
function encodeNum(num) {
  // verbose ascii code `ref${num}`;
  return `ref${num}`;
  // ascii codes
  //return num.toString().split('').map(i => encodeNumTable[i]).join('');
  // unicode codes
  // https://stackoverflow.com/questions/12746278/generate-a-list-of-unicode-characters-in-a-for-loop
  // String.fromCharCode(9728)
  // String.fromCharCode(9983)
  // https://stackoverflow.com/questions/43150498/how-to-get-all-unicode-characters-from-specific-categories
  // https://stackoverflow.com/questions/1337419/how-do-you-convert-numbers-between-different-bases-in-javascript
  // https://en.wikipedia.org/wiki/Miscellaneous_Symbols
  // 9728 = https://unicode-explorer.com/c/2600
  // 9728 + 255 = https://unicode-explorer.com/c/26FF

  // FIXME some codes are not translated @ single char unicode codes
  // expected range: 9728 to 9983
  // [♑] = 9809
  // [♳] = 9843
  // [☯]
  // [♎]
  // [♹]
  // [☧]

  // single char unicode codes
  const outputBase = 256;
  const digit = num % outputBase;
  return String.fromCharCode(9728 + digit);

  // convert base 10 to base 256
  /*
  const outputBase = 256;
  let result = [];
  do {
    const digit = num % outputBase;
    //const char = keys[digit];
    const char = String.fromCharCode(9728 + digit);
    result.push(char);
    num = Math.trunc(num / outputBase);
  } while (num != 0);
  return result.reverse().join("");
  */

  //return String.fromCharCode(9728 + (num % 256));
}

let decodeNumOffest = 0;
let decodeNumLastResult = 0;

// ascii codes
//const decodeNumTable = Object.fromEntries(codeNumKey.split('').map((c, i) => [c, i]));
function decodeNum(str) {
  //const numStr = str.replace(/\s+/sg, '').split('').map(c => decodeNumTable[c]).join('');
  // TODO also remove unicode spaces
  let numStr = str.replace(/\s+/sg, '');

  // verbose ascii code `ref${num}`;
  if (!numStr.match(/^ref[0-9]+$/)) {
    throw new Error(`decodeNum: invalid str: ${JSON.stringify(str)}`);
  }
  numStr = numStr.slice(4, -1);
  return parseInt(numStr);

  // unicode codes
  /*
  const inputBase = 256;
  //if (!numStr.match(/^[0-9]+$/)) {
  if (!numStr.match(/^[\u2600-\u26ff]+$/)) {
    throw new Error(`decodeNum: invalid str: ${JSON.stringify(str)}`);
  }
  const chars = numStr.split('');
  if (chars.length != 1) {
    throw new Error(`decodeNum: invalid str length: ${JSON.stringify(str)}`);
  }
  const char = chars[0];
  // 0 <= digit <= 255
  const digit = char.charCodeAt(0) - 9728;
  let result = decodeNumOffest + digit;
  if (result < (decodeNumLastResult - inputBase/2)) {
    // overflow
    result += inputBase;
    decodeNumOffest += inputBase;
  }
  decodeNumLastResult = result;
  return result;
  */
}

/*
// unicode
function decodeNumRaw(str) {
  const numStr = str.replace(/\s+/sg, '');
  if (!numStr.match(/^[\u2600-\u26ff]+$/u)) {
    throw new Error(`decodeNum: invalid str: ${JSON.stringify(str)}`);
  }
  const chars = numStr.split('');
  if (chars.length != 1) {
    throw new Error(`decodeNum: invalid str length: ${JSON.stringify(str)}`);
  }
  const char = chars[0];
  // 0 <= digit <= 255
  const digit = char.charCodeAt(0) - 9728;
  return digit;
}
*/

/*
// ok
// test
console.log(`testing encodeNum and decodeNum ...`)
// reset state of decodeNum
decodeNumOffest = 0;
decodeNumLastResult = 0;
for (let num = 0; num < 255*255*10; num++) {
  const code = encodeNum(num);
  const numActual = decodeNum(code);
  if (num != numActual) {
    console.error(`encodeNum or decodeNum failed: num=${num} code=${JSON.stringify(code)} numActual=${numActual}`)
    process.exit(1);
  }
}
// ok
console.log(`testing encodeNum and decodeNum done`)
// reset state of decodeNum
decodeNumOffest = 0;
decodeNumLastResult = 0;
for (const num of [0, 256-1, 256, 2*256-1, 2*256, 3*256-1, 3*256, 4*256-1, 4*256]) {
  const code = encodeNum(num);
  const numActual = decodeNum(code);
  console.log(`encodeNum(${num}) == ${JSON.stringify(code)}   decodeNum(${JSON.stringify(code)}) == ${numActual}`)
}
// reset state of decodeNum
decodeNumOffest = 0;
decodeNumLastResult = 0;
process.exit(0);
*/

const dryRunExport = 0;
const dryRunImport = 0;

const showDebug = 0;
//const showDebug = 1;

const charLimit = 5000; // limit of google, deepl
//const charLimit = 1000; // good page size for manual translations or debugging
//const charLimit = 1500; // deepl without login
// deepl rate limit: 4 requests, each 5000 chars
// Want to keep translating? Try DeepL Pro for free.
// You’ve reached your free usage limit.
// You can use the free version of DeepL again in 24 hours
// or try DeepL Pro to translate now and get premium features.

let useXml = false;

let translatorName = 'google';
//let translatorName = 'deepl';



const previewTextLength = 500;



/*

const fs = require('fs');
const path = require('path');

//const appRoot = require('app-root-path').path;

const glob = require('fast-glob');

// https://github.com/taoqf/node-html-parser
// https://github.com/taoqf/node-html-parser/pull/253
const { parse: parseHtml } = require('node-html-parser');

const htmlEntities = require('he');

// TODO
// google translate client
// https://github.com/thedaviddelta/lingva-scraper
const LingvaScraper = require('lingva-scraper');

// https://github.com/chge/tasty-treewalker
// https://stackoverflow.com/questions/39309351/dom-tree-walker-as-an-exercisejs
const tastyTreewalker = require('tasty-treewalker');

const crypto = require("crypto");

*/

import fs from 'fs';
import path from 'path';
import crypto from 'crypto';
import child_process from 'child_process';

//import { parse as parseHtml } from 'node-html-parser'; // TODO remove
//import * as htmlparser2 from "htmlparser2";

// concrete syntax tree parser for html
// https://github.com/lezer-parser/html
import { parser as lezerParserHtml } from '@lezer/html';

// https://github.com/milahu/nix-eval-js
// https://github.com/milahu/lezer-parser-nix
import { formatErrorContext } from './format-error-context.js';

import glob from 'fast-glob';
import htmlEntities from 'he';
//import LingvaScraper from 'lingva-scraper';
import { todo } from 'node:test'; // TODO what?

//console.log("htmlEntities.encode", htmlEntities.encode("&<>'\"")); process.exit()

// no, this is a polyfill for the browser
//import tastyTreewalker from 'tasty-treewalker';

// no. broken
//import HTMLtoDOCX from "html-to-docx";


//const elevConf = require(appRoot + '/config/eleventy.config.js')();

//process.chdir(appRoot);

//const scriptPath = path.relative(appRoot, process.argv[1]);

//const inputDir = elevConf.dir.input;
//const infilesGlob = inputDir + '/pages/'+'*.html';

//const infilesGlob = 'input.html';
const infilesGlob = '';

//const sourceLangList = ['de', 'en']; // TODO get from 11ty metadata



async function main() {

  const argv = process.argv.slice(1); // argv[0] is node

  const langMap = {
    zh: 'zh-CN', // simplified chinese
  };

  function getLang(str) {
    if (str && str in langMap) return langMap[str];
    return str;
  }

  // run this script from alchi/src/whoaremyfriends/
  //const inputPath = 'input.html';
  const inputPath = argv[1];

  const targetLang = getLang(argv[2]);

  const translationsPathList = argv.slice(3);

  if (!inputPath || !targetLang) {
    console.error(`error: missing arguments`);
    console.error(`usage:`);
    console.error(`# step 1: export text parts to a html file with links to translator`);
    console.error(`node translate-richtext.js input.html en`);
    console.error(`# step 2: import the translated text parts from a text file`);
    console.error(`node translate-richtext.js input.html en translations.txt`);
    return 1;
  }

  if (translationsPathList.length > 0) {
    return await importLang(inputPath, targetLang, translationsPathList);
  }
  else {
    return await exportLang(inputPath, targetLang);
  }
}





async function exportLang(inputPath, targetLang) {

  const inputHtml = fs.readFileSync(inputPath, 'utf8');

  // no. HTMLtoDOCX is broken: TypeError: Cannot read properties of undefined (reading 'colSpan')
  /*
  const headerHTMLString = null;
  const footerHTMLString = null;
  const documentOptions = {
    table: { row: { cantSplit: true } },
    footer: false,
    pageNumber: false,
  };
  const docxBuffer = await HTMLtoDOCX(inputHtml, headerHTMLString, documentOptions, footerHTMLString);
  const docxPath = inputPath + ".src.docx";
  fs.writeFileSync(docxPath, docxBuffer);
  console.log(`done ${docxPath}`);
  return 0;
  */

  // .slice(0, 50*1000);
  //const inputHtml = "<?xml a=\"b\"?><!doctype html><div id=\"asdf\" lang='foo'><a href=\"#\"><!-- my comment --></a></div>";

// debug...

// parse error
// -  <a class="nofootnote" href="https://www.youtube.com/watch?v=Cm_O97phbec&t=4566"
// +  <a class="nofootnote" href="https://www.youtube.com/watch?v=Cm_O97phbec&t=4566"t=4566"
// fixed by ignoring InvalidEntity
/*
const inputHtml = `
 <div>
   &mdash; Ken Jebsen im
  <a class="nofootnote" href="https://www.youtube.com/watch?v=Cm_O97phbec&t=4566"
   >100% Realtalk Podcast #72</a>
 </div>
`
*/

/*
const inputHtml = `
 <div>
   &mdash; Ken Jebsen im
  <a class="nofootnote" href="https://www.youtube.com/watch?v=Cm_O97phbec&t=4566&amp;foo"
   >100% Realtalk Podcast #72</a>
 </div>
`
*/

/*
const inputHtml = `
<html lang="de">
  <head>
    <title>asdf</title>
    <meta name="description" content="what">
    <meta name="author" content="who">
  </head>
</html>
`
*/

  // fixed in https://github.com/lezer-parser/html/pull/11
  /*
  console.error(`debug: position 50119+-5:\n-------------------------\n` + inputHtml.slice(50119 - 5, 50119 + 5) + '\n-------------------------')
  console.error(`debug: position 50119+-10:\n-------------------------\n` + inputHtml.slice(50119 - 10, 50119 + 10) + '\n-------------------------')
  console.error(`debug: position 50119+-20:\n-------------------------\n` + inputHtml.slice(50119 - 20, 50119 + 20) + '\n-------------------------')
  console.error(`debug: position 50119+-50:\n-------------------------\n` + inputHtml.slice(50119 - 50, 50119 + 50) + '\n-------------------------')
  //console.error(`debug: position 50119+-100:\n-------------------------\n` + inputHtml.slice(50119 - 100, 50119 + 100) + '\n-------------------------')
  */

  // node  5 = SelfClosingEndTag : "/>"                           : "/>"
  //const inputHtml = "<img><br/>";



  // freeze the input for later
  const inputHtmlHash = 'sha1-' + sha1sum(inputHtml);
  const inputPathFrozen = inputPath + '.' + inputHtmlHash;
  console.error(`writing ${inputPathFrozen}`);
  fs.writeFileSync(inputPathFrozen, inputHtml, 'utf8');



  //const translationsDatabaseJsonPath = 'translations-database.json';

  // TODO add sourceLang and targetLang to the file name
  //const translationsDatabaseHtmlPath = 'translations-database.html';

  // TODO add other translators: argos translate, deepl translator
  //const translationsDatabaseHtmlPathGlob = 'translations-database-*.html';
  const translationsDatabaseHtmlPathGlob = 'translations-google-database-*-*.html';

  const translationsDatabase = {};

  // parse translation databases
  for (const translationsDatabaseHtmlPath of glob.sync(translationsDatabaseHtmlPathGlob)) {
    console.log(`reading ${translationsDatabaseHtmlPath}`)
    const sizeBefore = Object.keys(translationsDatabase).length;
    parseTranslationsDatabase(translationsDatabase, fs.readFileSync(translationsDatabaseHtmlPath, 'utf8'));
    const sizeAfter = Object.keys(translationsDatabase).length;
    console.log(`loaded ${sizeAfter - sizeBefore} translations from ${translationsDatabaseHtmlPath}`)
  }

  // debug
  /*
  for (const key of Object.keys(translationsDatabase).slice(0, 10)) {
    console.log(`1010: translationsDatabase[${key}] = ${translationsDatabase[key]}`);
  }
  */



  // note: lezer-parser is a CONCRETE syntax tree parser == CST parser
  const htmlParser = lezerParserHtml.configure({
    // https://lezer.codemirror.net/docs/ref/#lr.ParserConfig
    // https://github.com/lezer-parser/html/blob/main/src/html.grammar
    // FIXME strict lezer-parser fails on large inputs. SyntaxError: No parse at 50119
    // TODO what is position 50119?
    //strict: true, // throw on parse error
    // fixed. dialect selfClosing is not working - parse error at SelfClosingEndTag
    // https://github.com/lezer-parser/html/issues/13
    // parse "/>" as SelfClosingEndTag
    // parse ">" as EndTag
    //dialect: "selfClosing",
    // TODO? dialect noMatch
  });

  let htmlTree;

  // parse input html
  try {
    htmlTree = htmlParser.parse(inputHtml);
  }
  catch (error) {
    // https://github.com/lezer-parser/lr/blob/main/src/parse.ts#L300
    if (error.message.startsWith("No parse at ")) {
      // note: pos is the character position, not the byte position
      const pos = parseInt(error.message.slice("No parse at ".length));
      error.message += '\n\n' + formatErrorContext(inputHtml, pos);
    }
    throw error;
  }

  const rootNode = htmlTree.topNode;


  //console.log(tree);



  // https://codereview.stackexchange.com/a/97886/205605
  // based on nix-eval-js/src/lezer-parser-nix/src/nix-format.js
  /** @param {Tree | TreeNode} tree */
  function walkHtmlTree(tree, func) {

    const cursor = tree.cursor();
    //if (!cursor) return '';
    if (!cursor) return;

    let depth = 0;

    while (true) {
      // NLR: Node, Left, Right
      // Node
      // NOTE InvalidEntity breaks the parser
      // <a t="a&amp;b&c">a&amp;b&c</a>
      // -> require valid input, throw on parse error
      const cursorTypeId = cursor.type.id;
      if (
        //true || // debug: dont filter
        !(
          cursorTypeId == 15 || // Document
          cursorTypeId == 20 || // Element
          cursorTypeId == 23 || // Attribute
          cursorTypeId == 21 || // OpenTag <script>
          cursorTypeId == 30 || // OpenTag <style>
          cursorTypeId == 36 || // OpenTag
          cursorTypeId == 32 || // CloseTag </style>
          cursorTypeId == 29 || // CloseTag </script>
          cursorTypeId == 37 || // CloseTag
          cursorTypeId == 38 || // SelfClosingTag
          // note: this is inconsistent in the parser
          // InvalidEntity is child node
          // EntityReference is separate node (sibling of other text nodes)
          cursorTypeId == 19 || // InvalidEntity: <a href="?a=1&b=2" -> "&" is parsed as InvalidEntity
          //cursorTypeId == 17 || // EntityReference: "&amp;" or "&mdash;" is parsed as EntityReference
          false
        )
      ) {
        func(cursor)
      }

      // Left
      if (cursor.firstChild()) {
        // moved down
        depth++;
        continue;
      }
      // Right
      if (depth > 0 && cursor.nextSibling()) {
        // moved right
        continue;
      }
      let continueMainLoop = false;
      let firstUp = true;
      while (cursor.parent()) {
        // moved up
        depth--;
        if (depth <= 0) {
          // when tree is a node, stop at the end of node
          // == dont visit sibling or parent nodes
          return;
        }
        if (cursor.nextSibling()) {
          // moved up + right
          continueMainLoop = true;
          break;
        }
        firstUp = false;
      }
      if (continueMainLoop) continue;
      break;
    }
  }



  // note: always set this to zero before calling walkHtmlTree
  let lastNodeTo = 0;

  const debugPrintAst = false;
  //const debugPrintAst = true;

  // debug: print the AST
  if (debugPrintAst) {
    lastNodeTo = 0;
    const maxLen = 30;
    walkHtmlTree(rootNode, (node) => {
      //const nodeSource = inputHtml.slice(lastNodeTo, node.to);
      let nodeSource = JSON.stringify(inputHtml.slice(node.from, node.to));
      let spaceNodeSource = JSON.stringify(inputHtml.slice(lastNodeTo, node.to));
      if (nodeSource.length > maxLen) {
        nodeSource = nodeSource.slice(0, maxLen);
      }
      if (spaceNodeSource.length > maxLen) {
        spaceNodeSource = spaceNodeSource.slice(0, maxLen);
      }
      //console.log(`${node.from}: node ${node.type.id} = ${node.type.name}: ${nodeSource.length}: ${nodeSource.slice(0, 100)}...`)
      //console.log(`${node.from}: node ${node.type.id} = ${node.type.name}: ${nodeSource.length}: ${JSON.stringify(nodeSource)}`)
      //console.log(`${node.from}: node ${node.type.id} = ${node.type.name}: ${JSON.stringify(nodeSource)}`)
      //console.log(`node ${node.type.id} = ${node.type.name}: ${JSON.stringify(nodeSource)}`)
      // TODO better. wrap string in single quotes
      // similar to python repr(...)
      //const s = "'" + JSON.stringify(nodeSource).slice(1, -1).replace(/\\"/g, '"') + "'";
      //const s = JSON.stringify(nodeSource).slice(0, 100);
      console.log(`node ${String(node.type.id).padStart(2)} = ${node.type.name.padEnd(25)} : ${nodeSource.padEnd(maxLen)} : ${spaceNodeSource}`);
      lastNodeTo = node.to;
    });
    return;
  }



  const checkParserLossless = false;
  //const checkParserLossless = true;

  if (checkParserLossless) {

    // test the tree walker
    // this test run should return
    // the exact same string as the input string
    // = lossless noop

    let walkHtmlTreeTestResult = "";
    lastNodeTo = 0;
    walkHtmlTree(rootNode, (node) => {
      const nodeSource = inputHtml.slice(lastNodeTo, node.to);
      walkHtmlTreeTestResult += nodeSource;
      lastNodeTo = node.to;
      // debug: print the AST
      //const s = JSON.stringify(nodeSource).slice(0, 100);
      //console.log(`node ${node.type.id} = ${node.type.name}: ${s}`);
    });

    if (walkHtmlTreeTestResult != inputHtml) {
      console.error('error: the tree walker is not lossless');

      const inputPathFrozenError = inputPath + '.' + inputHtmlHash + '.error';
      console.error(`writing ${inputPathFrozenError}`);
      fs.writeFileSync(inputPathFrozenError, walkHtmlTreeTestResult, 'utf8');

      console.error(`TODO: diff -u ${inputPathFrozen} ${inputPathFrozenError}`);
      console.error(`TODO: fix the tree walker`);

      process.exit(1);
    }

    console.error(`ok. the tree walker is lossless`);
    walkHtmlTreeTestResult = "";

    //return;

  }



  /*
  let currentTagName = undefined;
  */
  //function newTag(parent) {
  function newTag() {
    const tag = {
      openSpace: null,
      open: null,
      nameSpace: null,
      name: null,
      attrs: [],
      classList: [],
      parent: null,
      lang: null,
      ol: null, // original language
      // this tag (or a parent tag) has one of these attributes:
      //   class="... notranslate ..."
      //   style="... display:none ..."
      notranslate: false,
      hasTranslation: false, // tag has attribute: src-lang-id="en:some-id"
    };
    return tag;
  }

  lastNodeTo = 0;
  let inNotranslateBlock = false;
  let currentTag = undefined;
  let attrName = undefined;
  let attrNameSpace = "";
  let attrIs = undefined;
  let attrIsSpace = "";
  let attrValueQuoted = undefined;
  let attrValue = undefined;
  let currentLang = undefined;
  const textToTranslateList = [];
  let outputTemplateHtml = "";
  let tagPath = [];
  let inStartTag = false;
  let startTagNodes = [];
  const htmlBetweenReplacementsList = [];
  let lastReplacementEnd = 0;
  let inAttributeValue = false;

  // https://html.spec.whatwg.org/multipage/syntax.html#void-elements
  const selfClosingTagNameSet = new Set([
    "area", "base", "br", "col", "embed", "hr", "img",
    "input", "link", "meta", "source", "track", "wbr"
  ]);

  function isSelfClosingTagName(tagName) {
    // note: this is case sensitive
    // ideally this would use tagName.toLowerCase()
    return selfClosingTagNameSet.has(tagName);
  }

  function trimNodeSource(str) {
    return str.replace(/\s+/g, " ").trim();
  }

  function isSentenceTag(currentTag) {
    // TODO nested tags? <li><a>asdf</a></li> should become "asdf."
    return currentTag.name.match(/^(title|h[1-9]|div|li|td)$/) != null;
  }

  function nodeSourceIsEndOfSentence(nodeSource) {
    return nodeSource.match(/[.!?]["]?\s*$/s) != null;
  }

  function shouldTranslateCurrentTag(currentTag, inNotranslateBlock, currentLang, targetLang) {
    return (
      inNotranslateBlock == false &&
      currentTag.notranslate != true &&
      // TODO remove. moved to currentTag.notranslate
      //currentTag.hasTranslation == false &&
      currentTag.lang != targetLang
      // TODO remove. lang inheritance moved to newTag()
      //currentLang != targetLang
    );
  }

  function writeComment(...a) {
    return;
    const s = a.map(String).join(" ");
    outputTemplateHtml += "\n<!-- " + s + " -->\n";
  }

  // walkHtmlTree rootNode
  walkHtmlTree(rootNode, (node) => {
    //console.log(node);

    //console.log("node", node);
    //console.log("node.name", node.type.name);
    //console.log("node.type.name", node.type.name);
    //console.log("node.type.id", node.type.id);
    //console.log("node.from + to", node.from, node.to);

    //console.log("node.rawTagName", node.rawTagName);

    //console.log("node.toString", node.toString());

    //const nodeSource = inputHtml.slice(node.from, node.to);
    let nodeSource = inputHtml.slice(node.from, node.to);
    let nodeSourceSpaceBefore = inputHtml.slice(lastNodeTo, node.from);

    //console.log("nodeSource", nodeSource);
    //console.log("nodeSource:", { lastNodeTo, nodeFrom: node.from, nodeTo: node.to, nodeSourceSpaceBefore, nodeSource });
    // debug
    false && console.log("node:", {
      typeId: node.type.id,
      typeName: node.type.name,
      lastNodeTo,
      nodeFrom: node.from,
      nodeTo: node.to,
      nodeSourceSpaceBefore,
      nodeSource,
    });

    // validate nodeSourceSpaceBefore
    if (nodeSourceSpaceBefore.match(/^\s*$/) == null) {
      console.error((
        `error: nodeSourceSpaceBefore must match the regex "\\s*". ` +
        `hint: add "lastNodeTo = node.to;" before "return;"`
      ), {
        lastNodeTo,
        nodeFrom: node.from,
        nodeTo: node.to,
        nodeSourceSpaceBefore,
        nodeSource,
        nodeSourceContext: inputHtml.slice(node.from - 100, node.to + 100),
      })
      process.exit(1);
    }

    if (nodeSource == '<!-- <notranslate> -->') {
      inNotranslateBlock = true;
      outputTemplateHtml += `${nodeSourceSpaceBefore}${nodeSource}`;
      lastNodeTo = node.to;
      return;
    }
    else if (nodeSource == '<!-- </notranslate> -->') {
      inNotranslateBlock = false;
      outputTemplateHtml += `${nodeSourceSpaceBefore}${nodeSource}`;
      lastNodeTo = node.to;
      return;
    }

    const nodeTypeId = node.type.id;
    const nodeTypeName = node.type.name;

    /*
    6 = StartTag: <
    22 = TagName: html
    24 = AttributeName:  lang
    25 = Is: =
    26 = AttributeValue: "de"
    4 = EndTag: >
    */

    // start of open tag
    // "<"
    if (
      nodeTypeName == "StartTag"
      /*
      nodeTypeId == 6 ||
      nodeTypeId == 7 || // <script>
      nodeTypeId == 10 || // <link>
      false
      */
    ) {
      if (
        !(
          nodeTypeId == 6 ||
          nodeTypeId == 7 || // <script>
          nodeTypeId == 8 || // <style>
          nodeTypeId == 10 || // <link>
          false
        )
      ) {
        console.error(`TODO implement: StartTag with nodeTypeId=${nodeTypeId}`);
        process.exit(1);
      }
      const parentTag = currentTag;
      currentTag = newTag();
      if (parentTag) {
        // inherit notranslate from parent
        // TODO if (notranslate == true) then notranslate should be read-only
        // so when (notranslate == true) then all child nodes are not translated
        currentTag.notranslate = parentTag.notranslate;
        currentTag.lang = parentTag.lang;
        currentTag.parent = parentTag;
      }
      // no. notranslate blocks are outside of the html node tree
      // if (inNotranslateBlock) {
      //   currentTag.notranslate = true;
      // }
      tagPath.push(currentTag);
      inStartTag = true;
      // not needed?
      // buffer the StartTag nodes before output
      // so we can modify nodes like the AttributeName + AttributeValue nodes lang="..."
      //startTagNodes = [];

      currentTag.openSpace = nodeSourceSpaceBefore;
      currentTag.open = nodeSource;

      // don't write. wait for end of start tag
      lastNodeTo = node.to;
      return;
    }

    // start of close tag
    // "</"
    else if (
      nodeTypeName == "StartCloseTag"
    ) {
      if (
        isSentenceTag(currentTag)
      ) {
        // add "." for joinText, so the translator can split sentences
        textToTranslateList.push([
          textToTranslateList.length, // textIdx
          "", // nodeSourceTrimmedHash
          currentLang,
          ".", // nodeSourceTrimmed
          1, // todoRemoveEndOfSentence
          0, // todoAddToTranslationsDatabase
        ]);
        htmlBetweenReplacementsList.push("");
      }
    }

    // elif node_type_id == node_kind[">"] or node_type_id == node_kind["/>"]:
    else if (
      //nodeTypeName == "EndTag"
      nodeTypeId == 4
    ) { // EndTag of StartTag or StartCloseTag
      inAttributeValue = false;
      /*
      if (nodeTypeId != 4) {
        console.error(`TODO implement: EndTag with nodeTypeId=${nodeTypeId}`);
        process.exit(1);
      }
      */

      if (inStartTag) {
        // end of start tag
        if (showDebug) {
          console.log(`node ${nodeTypeId}: end of start tag -> inStartTag=False`);
        }
        // process and write the start tag

        writeComment(JSON.stringify({
          "tagPath": tagPath.map(t => "/" + (t.name || "(noname)")).join(""),
          "currentTag.name": currentTag.name,
          "currentTag.notranslate": currentTag.notranslate,
          "currentTag.attrs": currentTag.attrs.map(a => a.join("")),
        }, null, 2));

        // write " <someName"
        outputTemplateHtml += (
          // " <"
          currentTag.openSpace + currentTag.open +
          // "someName"
          currentTag.nameSpace + currentTag.name +
          ""
        );

        //if (currentTag.notranslate) {
        if (!shouldTranslateCurrentTag(currentTag, inNotranslateBlock, currentLang, targetLang)) {
          // preserve attributes
          currentTag.attrs.forEach(attrItem => {
            outputTemplateHtml += attrItem.join("");
          });
        } else {
          // modify attributes
          currentTag.attrs.forEach(attrItem => {
            let [
              attrNameSpace,
              attrName,
              attrIsSpace,
              attrIs,
              attrValueSpace,
              attrValueQuote,
              attrValue,
              attrValueQuote2
            ] = attrItem;

            // modify attribute
            if (attrName === "lang") {
              attrValue = targetLang;
            }



            // translate the AttributeValue in some cases
            // <meta name="description" content="...">
            // <meta name="keywords" content="...">
            // <div title="...">...</div>
            // other <meta> tags are already guarded by <notranslate>
            if (
              (translateTitleAttr && attrName == "title") ||
              (translateMetaContent && currentTag.name == 'meta' && attrName == "content") ||
              false
            ) {
              //const metaName = (currentTag.attrs.find(([name, _value]) => name == "name") || [])[1];
              //const metaContent = (currentTag.attrs.find(([name, _value]) => name == "content") || [])[1];
              //if (metaName && metaContent) {
              //console.log(`TODO translate this meta tag`);
              // TODO future: add/replace attribute: data-sl="de#somehash" or data-sl="en#somehash"
              // TODO future: remove the "lang" attribute
              // if the tag has the same language as the document <html lang="...">
              // sl = source language
              // somehash = the sha1 hash of the trimmed source
              //outputHtml += nodeSource;
              // TODO tolerate collisions from trimming whitespace?
              //const nodeSourceTrimmed = trimNodeSource(nodeSource);

              let attrValueHash = sha1sum(attrValue);
              let textIdx = textToTranslateList.length;
              let nodeSourceKey = `${textIdx}_${currentLang}_${attrValueHash}`;
              let todoRemoveEndOfSentence = 0;

              if (!nodeSourceIsEndOfSentence(attrValue)) {
                attrValue += ".";
                todoRemoveEndOfSentence = 1;
              }

              const translationKey = currentLang + ":" + targetLang + ":" + attrValueHash;

              const todoAddToTranslationsDatabase = (translationKey in translationsDatabase) ? 0 : 1;

              if (currentLang === null) {
                let sourceStart = nodeSource.slice(0, 100);
                // TODO show "outerHTML". this is only the text node
                throw new Error(`node has no lang attribute: ${sourceStart}`);
              }

              let textToTranslate = [
                textIdx,
                attrValueHash,
                currentLang,
                attrValue,
                todoRemoveEndOfSentence,
                todoAddToTranslationsDatabase,
              ];

              textToTranslateList.push(textToTranslate);

              // store outputHtml between the last replacement and this replacment
              const htmlBetweenReplacements = [
                outputTemplateHtml.slice(lastReplacementEnd), // wrong?
                attrNameSpace,
                attrName,
                attrIsSpace,
                attrIs,
                attrValueSpace,
                attrValueQuote,
                //attrValue,
                //attrValueQuote,
              ].join("");
              if (showDebug) {
                console.log(1170, "htmlBetweenReplacementsList.push", JSON.stringify(htmlBetweenReplacements));
              }
              htmlBetweenReplacementsList.push(htmlBetweenReplacements);

              attrValue = `{TODO_translate_${nodeSourceKey}}`;

              // store end position of attrValue
              //lastReplacementEnd = outputTemplateHtml.length + (attrNameSpace + attrName + attrIsSpace + attrIs + attrValueSpace + attrValueQuote + attrValue).length;
              lastReplacementEnd = lastReplacementEnd + htmlBetweenReplacements.length + attrValue.length;
              // lastReplacementEnd = lastReplacementEnd + ([
              //   //outputTemplateHtml.slice(lastReplacementEnd),
              //   attrNameSpace,
              //   attrName,
              //   attrIsSpace,
              //   attrIs,
              //   attrValueSpace,
              //   attrValueQuote,
              //   attrValue,
              //   //attrValueQuote,
              // ].join("")).length;
            }



            // write attribute
            let newAttrItem = [
              attrNameSpace,
              attrName,
              attrIsSpace,
              attrIs,
              attrValueSpace,
              attrValueQuote,
              attrValue,
              attrValueQuote,
            ];
            outputTemplateHtml += newAttrItem.join("");

            if (
              attrName === "lang" &&
              currentTag.lang != targetLang &&
              currentTag.ol === null
            ) {
              // add "ol" attribute after "lang" attribute
              outputTemplateHtml += ` ol="${currentTag.lang}"`;
            }
          });
        }
      }



      if (
        // self-closing tag "<br>"
        (
          inStartTag == true &&
          isSelfClosingTagName(currentTag.name)
        ) ||
        // close tag "</div>"
        inStartTag == false
      ) {
        tagPath.pop();
        //console.error(`- tagPath=/${tagPath.map(tag => tag.name).join('/')}`)
        currentTag = tagPath[tagPath.length - 1];
        // set currentLang of next parent tag with (tag.lang != undefined)
        // TODO remove. lang inheritance moved to newTag()
        currentLang = undefined;
        for (let i = tagPath.length - 1; i >= 0; i--) {
          if (tagPath[i].lang) {
            currentLang = tagPath[i].lang;
            break;
          }
        }
      }
      inStartTag = false;
    }

    // TagName in StartTag
    else if (inStartTag && nodeTypeId == 22) {
      currentTag.nameSpace = nodeSourceSpaceBefore;
      currentTag.name = nodeSource;
      //console.error(`+ tagPath=/${tagPath.map(tag => tag.name).join('/')}`)
      if (inStartTag) {
        // dont write. wait for end of start tag
        lastNodeTo = node.to;
        return;
      }
    }

    // AttributeName in StartTag
    else if (nodeTypeId == 24) {
      inAttributeValue = false;
      attrName = nodeSource;
      attrNameSpace = nodeSourceSpaceBefore;
      // dont write. wait for end of start tag
      lastNodeTo = node.to;
      return;
    }
    // Is ("=") in StartTag
    else if (inStartTag && nodeTypeName == "Is") {
      // dont write. wait for end of start tag
      attrIs = nodeSource;
      attrIsSpace = nodeSourceSpaceBefore;
      lastNodeTo = node.to;
      return;
    }
    // AttributeValue in StartTag
    else if (nodeTypeId == 26) {
      // needed to filter EntityReference in AttributeValue
      inAttributeValue = true;
      const attrValueSpace = nodeSourceSpaceBefore;
      const attrValueQuote = (
        (
          nodeSource[0] == "'" ||
          nodeSource[0] == '"'
        ) ? nodeSource[0] // value is quoted
        : "" // value is unquoted
      );
      attrValueQuoted = nodeSource;
      attrValue = (attrValueQuote == "") ? nodeSource : nodeSource.slice(1, -1);
      // TODO push all tokens
      //currentTag.attrs.push([attrName, attrValueQuoted]);
      const attrItem = [
        attrNameSpace,
        attrName,
        attrIsSpace,
        attrIs,
        attrValueSpace,
        attrValueQuote,
        attrValue,
        attrValueQuote,
      ];
      // current_tag.attrs.append(attr_item)
      currentTag.attrs.push(attrItem);

      //console.log(`${nodeTypeId} = ${node.type.name}: attrName=${attrName}`);

      // if attr_name == "lang":
      //     current_tag.lang = attr_value
      //     current_lang = attr_value
      //     if current_tag.lang == target_lang:
      //         current_tag.notranslate = True

      if (attrName == "lang") {
        // slice(1, -1): remove quotes from "some_value"
        currentTag.lang = attrValue;
        currentLang = currentTag.lang;

        // not: modify the source
        // no, do this later
        /*
        // debug
        console.log(`- ${nodeTypeId} = ${node.type.name}: ${nodeSource}`);
        console.log(`+ ${nodeTypeId} = ${node.type.name}: "newlang"`);
        lastNodeTo = node.to;
        return;
        */

        //     if current_tag.lang == target_lang:
        //         current_tag.notranslate = True

        // no. wrong!
        // TODO move
        // if (currentLang == targetLang) {
        //   currentTag.notranslate = true;
        // }

// TODO move
        // if (currentLang != targetLang) {
        //   const nodeSourceNew = attrValueQuote + targetLang + attrValueQuote;
        //   // modify the lang="..." attribute
        //   // debug
        //   false && console.log(`AttributeValue:`, {
        //     attrNameSpace, attrName,
        //     attrIsSpace, attrIs,
        //     nodeSourceSpaceBefore, nodeSourceNew,
        //   })
        //   outputTemplateHtml += (
        //     attrNameSpace + attrName +
        //     attrIsSpace + attrIs +
        //     nodeSourceSpaceBefore + nodeSourceNew
        //   );
        //   // stop processing this AttributeValue
        //   lastNodeTo = node.to;
        //   return;
        // }

        // else: currentLang == targetLang
        // -> keep the lang="..." attribute
        // TODO verify
        /*
        else {
          // clear the output buffer
          outputHtml += (
            attrNameSpace + attrName +
            attrIsSpace + attrIs
          );
        }
        */
      }

      // # ol = original language
      // elif attr_name == "ol":
      //     current_tag.ol = attr_value

      else if (attrName == "ol") {
        currentTag.ol = attrValue;
      }



      // # ignore tags with attribute: class="notranslate"
      // elif attr_name == "class":
      //     #class_list = set(attr_value.split())
      //     class_list = attr_value.split()
      //     current_tag.class_list += class_list
      //     if "notranslate" in class_list:
      //         current_tag.notranslate = True

      // ignore tags with attribute: class="notranslate"
      else if (attrName == "class") {
        //const classList = new Set(attrValue.split(/\s+/).filter(Boolean));
        const classList = attrValue.split(/\s+/).filter(Boolean);
        //console.dir({ attrValueQuoted, classList: Array.from(classList) })

        currentTag.classList.push(...classList);

        //if (classList.has("notranslate")) {
        if (classList.includes("notranslate")) {
          currentTag.notranslate = true;
          // TODO move
          // // stop processing this AttributeValue
          // outputTemplateHtml += (
          //   attrNameSpace + attrName +
          //   attrIsSpace + attrIs +
          //   nodeSourceSpaceBefore + nodeSource
          // );
          // lastNodeTo = node.to;
          // return;
        }
      }



      // # ignore tags with attribute: src-lang-id="..."
      // elif attr_name == "src-lang-id":
      //     if attr_value.startswith(target_lang + ":"):
      //         #current_tag.has_translation = True
      //         current_tag.notranslate = True

      // ignore tags with attribute: src-lang-id="..."
      else if (attrName == "src-lang-id") {
        if (attrValue.startsWith(targetLang + ":")) {
          // src-lang-id="en:some-id"
          //currentTag.hasTranslation = true;
          currentTag.notranslate = true;
          // TODO move
          // // stop processing this AttributeValue
          // outputTemplateHtml += (
          //   attrNameSpace + attrName +
          //   attrIsSpace + attrIs +
          //   nodeSourceSpaceBefore + nodeSource
          // );
          // lastNodeTo = node.to;
          // return;
        }
      }



      // # ignore tags with attribute: style="display:none"
      // # TODO also ignore all child nodes of such tags
      // elif attr_name == "style":
      //     # TODO parse CSS. this can be something stupid like
      //     # style="/*display:none*/"
      //     # TODO regex
      //     # currentAttrValue.match(/.*\b(display\s*:\s*none)\b.*/s) != null
      //     if attr_value == "display:none" or "display: none" in attr_value:
      //         current_tag.notranslate = True

      // ignore tags with attribute: style="display:none"
      // TODO also ignore all child nodes of such tags
      else if (attrName == "style") {
        if (
          //attrValue == "display:none" ||
          // TODO parse CSS. this can be something stupid like
          // style="/*display:none*/"
          // \b = word boundary
          attrValue.match(/.*\b(display\s*:\s*none)\b.*/s) != null
        ) {
          // TODO inherit this to all child nodes
          currentTag.notranslate = true;

          // // stop processing this AttributeValue
          // outputTemplateHtml += (
          //   attrNameSpace + attrName +
          //   attrIsSpace + attrIs +
          //   nodeSourceSpaceBefore + nodeSource
          // );
          // lastNodeTo = node.to;
          // return;
        }
      }

      /*
      else {
        // clear the output buffer
        outputHtml += (
          attrNameSpace + attrName +
          attrIsSpace + attrIs
        );
      }
      */


      // #print("attr_name", __line__(), repr(attr_name))

      // attr_name = None

      // # dont write. wait for end of start tag
      // last_node_to = node.range.end_byte
      // continue
      lastNodeTo = node.to;
      return;

      // // clear the output buffer
      // outputTemplateHtml += (
      //   attrNameSpace + attrName +
      //   attrIsSpace + attrIs
      // );

    }

    /*
    // this should be lossless
    //process.stdout.write(nodeSource);
    walkHtmlTreeTestResult += nodeSource;
    lastNodeTo = node.to;
    return;
    */

    // filter EntityReference in AttributeValue
    // for now, this is only needed for lezer-parser-html
    // see also
    // https://github.com/tree-sitter/tree-sitter-html/issues/51
    if (
      nodeTypeId == 17 || // EntityReference
      false
    ) {
      if (inAttributeValue) {
        // EntityReference is already in AttributeValue
        // so dont copy the EntityReference
        // but when in a text node
        // copy the EntityReference
        return;
      }
    }

    if (
      nodeTypeId == 16 || // Text
      // no. never translate &some_entity; and <script> and <style>
      // TODO for the "joined" translation, decode entities to unicode chars
      // example: &mdash; -> \u2014 https://www.compart.com/en/unicode/U+2014
      // example: &amp; -> &
      // ... but we have to locate and revert these replacements via the "splitted" translation
      //nodeTypeId == 17 || // EntityReference // "&amp;" or "&mdash;" or ...
      //nodeTypeId == 28 || // ScriptText
      //nodeTypeId == 31 || // StyleText
      false
    ) {
      //if (nodeSource.match(/^\s+$/s)) {
      if ((nodeSourceSpaceBefore + nodeSource).match(/^\s+$/s)) {
        //console.log(`${nodeTypeId} = ${node.type.name} (whitespace): ${nodeSource}`);
        //console.log(`tagPath=/${tagPath.map(tag => tag.name).join('/')}: lang=${currentLang}: type=${nodeTypeId}=${node.type.name}=whitespace: ${(nodeSourceSpaceBefore + nodeSource)}`);
        outputTemplateHtml += nodeSourceSpaceBefore + nodeSource;
        lastNodeTo = node.to;
        return;
      }

      if (shouldTranslateCurrentTag(currentTag, inNotranslateBlock, currentLang, targetLang)) {
      //if (currentTag.notranslate == false && currentLang != targetLang) {
        // TODO also compare source and target language
        // if they are equal, no need to translate
        // TODO remove whitespace? trimNodeSource
        let nodeSourceTrimmed = nodeSource;
        const nodeSourceTrimmedHash = sha1sum(nodeSourceTrimmed);
        const textIdx = textToTranslateList.length;
        const nodeSourceKey = `${textIdx}_${currentLang}_${nodeSourceTrimmedHash}`;
        let todoRemoveEndOfSentence = 0;

        // no. one node can have multiple text child nodes
        // example: Text EntityReference Text
        // fix: add "." only before StartCloseTag
        /*
        if (
          nodeSourceIsEndOfSentence(nodeSourceTrimmed) == false &&
          isSentenceTag(currentTag)
        ) {
          nodeSourceTrimmed += ".";
          todoRemoveEndOfSentence = 1;
        }
        */

        const translationKey = currentLang + ":" + targetLang + ":" + nodeSourceTrimmedHash;

        const todoAddToTranslationsDatabase = (
          translationsDatabase.hasOwnProperty(translationKey) == false
        ) ? 1 : 0;

        const textToTranslate = [
          textIdx,
          nodeSourceTrimmedHash,
          currentLang,
          nodeSourceTrimmed,
          todoRemoveEndOfSentence,
          todoAddToTranslationsDatabase,
        ];

        textToTranslateList.push(textToTranslate);

        // console.dir({ translationKey, textToTranslateList }); throw new Error("todo");

        const htmlBetweenReplacements = (
          outputTemplateHtml.slice(lastReplacementEnd) + nodeSourceSpaceBefore
        );

        if (showDebug) {
          console.log(1570, "htmlBetweenReplacementsList.push", JSON.stringify(htmlBetweenReplacements));
        }

        // store outputHtml between the last replacement and this replacment
        htmlBetweenReplacementsList.push(htmlBetweenReplacements);
        // TODO store context of replacement: attribute value with quotes (single or double quotes?)
        // then escape the quotes in the translated text
        outputTemplateHtml += `${nodeSourceSpaceBefore}{TODO_translate_${nodeSourceKey}}`;
        lastReplacementEnd = outputTemplateHtml.length;
        lastNodeTo = node.to;
        return;
      }
    }

    if (nodeTypeId == 39) { // Comment
      if (
        translateComments == false ||
        shouldTranslateCurrentTag(currentTag, inNotranslateBlock, currentLang, targetLang) == false
      ) {
        outputTemplateHtml += nodeSourceSpaceBefore + nodeSource;
        lastNodeTo = node.to;
        return;
      }

      const commentContentWithPrefix = nodeSource.slice(4, -3);
      const commentLangMatch = commentContentWithPrefix.match(/\(lang="([a-z+]{2,100})"\)/);
      const commentLang = commentLangMatch ? commentLangMatch[1] : undefined;
      const commentLangPrefix = commentLangMatch ? commentLangMatch[0] : "";
      const commentContent = commentContentWithPrefix.slice(commentLangPrefix.length);

      //if (nodeSource.match(/^\s+$/s)) {
      if ((nodeSourceSpaceBefore + commentContent).match(/^\s+$/s)) {
        //console.log(`${nodeTypeId} = ${node.type.name} (whitespace): ${nodeSource}`);
        //console.log(`tagPath=/${tagPath.map(tag => tag.name).join('/')}: lang=${currentLang}: type=${nodeTypeId}=${node.type.name}=whitespace: ${(nodeSourceSpaceBefore + nodeSource)}`);
        outputTemplateHtml += nodeSourceSpaceBefore + nodeSource;
        lastNodeTo = node.to;
        return;
      }

      if (shouldTranslateCurrentTag(currentTag, inNotranslateBlock, currentLang, targetLang)) {
      //if (currentTag.notranslate == false && currentLang != targetLang) {
        // TODO also compare source and target language
        // if they are equal, no need to translate
        let nodeSourceTrimmed = commentContent;
        const nodeSourceTrimmedHash = sha1sum(nodeSourceTrimmed);
        const textIdx = textToTranslateList.length;
        const nodeSourceKey = `${textIdx}_${commentLang || currentLang}_${nodeSourceTrimmedHash}`;
        let todoRemoveEndOfSentence = 0;

        if (
          nodeSourceIsEndOfSentence(nodeSourceTrimmed) == false &&
          isSentenceTag(currentTag)
        ) {
          nodeSourceTrimmed += ".";
          todoRemoveEndOfSentence = 1;
        }

        const translationKey = currentLang + ":" + targetLang + ":" + nodeSourceTrimmedHash;

        const todoAddToTranslationsDatabase = (
          translationsDatabase.hasOwnProperty(translationKey) == false
        ) ? 1 : 0;

        const textToTranslate = [
          textIdx,
          nodeSourceTrimmedHash,
          currentLang,
          nodeSourceTrimmed,
          todoRemoveEndOfSentence,
          todoAddToTranslationsDatabase,
        ]

        textToTranslateList.push(textToTranslate);

        const htmlBetweenReplacements = (
          outputTemplateHtml.slice(lastReplacementEnd) + nodeSourceSpaceBefore + '<!--'
        );

        if (showDebug) {
          console.log(1640, "htmlBetweenReplacementsList.push", JSON.stringify(htmlBetweenReplacements));
        }

        // store outputHtml between the last replacement and this replacment
        htmlBetweenReplacementsList.push(htmlBetweenReplacements);
        // TODO store context of replacement: attribute value with quotes (single or double quotes?)
        // then escape the quotes in the translated text
        outputTemplateHtml += `${nodeSourceSpaceBefore}<!--{TODO_translate_${nodeSourceKey}}-->`;
        lastReplacementEnd = outputTemplateHtml.length - 3;
        lastNodeTo = node.to;
        return;
      }

    }

    // default: copy this node
    //console.log(`${nodeTypeId} = ${node.type.name}: ${nodeSource}`);
    //console.log(`tagPath=/${tagPath.map(tag => tag.name).join('/')}: lang=${currentLang}: type=${nodeTypeId}=${node.type.name}: ${(nodeSourceSpaceBefore + nodeSource)}`);
    outputTemplateHtml += nodeSourceSpaceBefore + nodeSource;
    lastNodeTo = node.to;
    return;

    //console.log();
  });
  // walkHtmlTree rootNode end

  // html after the last replacement
  const htmlBetweenReplacements = (
    outputTemplateHtml.slice(lastReplacementEnd)
  );
  if (showDebug) {
    console.log(1670, "htmlBetweenReplacementsList.push", JSON.stringify(htmlBetweenReplacements));
  }
  htmlBetweenReplacementsList.push(htmlBetweenReplacements);

  const outputTemplateHtmlPath = inputPath + '.' + inputHtmlHash + '.outputTemplate.html';
  console.error(`writing ${outputTemplateHtmlPath}`);
  fs.writeFileSync(outputTemplateHtmlPath, outputTemplateHtml, 'utf8');

  const textToTranslateListPath = inputPath + '.' + inputHtmlHash + '.textToTranslateList.json';
  console.error(`writing ${textToTranslateListPath}`);
  fs.writeFileSync(textToTranslateListPath, JSON.stringify(textToTranslateList, null, 2), "utf8");
  // jsonlines-like format
  //fs.writeFileSync(textToTranslateListPath, '[\n' + textToTranslateList.map(entry => JSON.stringify(entry)).join(',\n') + '\n]', "utf8");

  const htmlBetweenReplacementsPath = inputPath + '.' + inputHtmlHash + '.htmlBetweenReplacementsList.json';
  console.error(`writing ${htmlBetweenReplacementsPath}`);
  fs.writeFileSync(htmlBetweenReplacementsPath, JSON.stringify(htmlBetweenReplacementsList, null, 2), "utf8");



  // TODO build chunks of same language
  // limited by charLimit = 5000



  // new code -> old code
  // textToTranslateList -> textParts




  const replacementData = {};
  //replacementData.replacementList = [];
  replacementData.replacementList = {}; // sparse array due to "safe" ids, see getNextSafeId
  //replacementData.indentList = [];
  replacementData.lastId = -1;
  let replacementData_lastId_2 = -1;

  // function fmtNum(num) {
  //   // split long number in groups of three digits
  //   // https://stackoverflow.com/a/6786040/10440128
  //   return `${num}`.replace(/(\d)(?=(\d{3})+$)/g, '$1 ');
  // }

  function getReplace(match) {
    // global: replacementData
    /*
    const replacementId = getNextSafeId(replacementData.lastId);
    replacementData.lastId = replacementId;
    */
    //const replacementId = (replacementData.lastId + 1) % 256;
    const replacementId = replacementData.lastId + 1;
    replacementData.lastId = replacementId;
    const code = encodeNum(replacementId);
    replacementData.replacementList[replacementId] = {};
    replacementData.replacementList[replacementId].value = match;
    replacementData.replacementList[replacementId].code = code;
    replacementData.replacementList[replacementId].indentList = [];
    // dont add newlines
    // to google translate, newline means "new sentence"
    // so extra newlines break the context of words
    //return `\n[${code}]\n`;
    return ` [${code}] `;
  }



  const textPartsByLang = {};
  const textPartRawListByLang = {};
  //const textPartsByPos = [];

  // loop textToTranslateList
  for (const textToTranslate of textToTranslateList) {

    // textToTranslateList.push([
    //   textIdx,
    //   nodeSourceTrimmedHash,
    //   currentLang,
    //   nodeSourceTrimmed,
    //   todoRemoveEndOfSentence,
    //   todoAddToTranslationsDatabase,
    // ]);

    const todoAddToTranslationsDatabase = textToTranslate[5];
    if (todoAddToTranslationsDatabase == 0) {
      // filter. dont send this source text to the translator
      // note: add="${textToTranslate[5]}" is always add="1"
      continue;
    }

    // why so complex? why do we wrap text in <html>...</html> tags?
    // because we have two levels of replacements?
    // 1. replace text blocks
    // 2. replace special text parts (html tags, whitespace) in the text blocks
    // also because we send lines to the translator, to get the "splitted" translation
    // so we need a way to encode text blocks

    //console.log(`textToTranslate[3]`, JSON.stringify(textToTranslate[3])); // debug

    // TODO? add source language sl="..."
    const textToTranslateHtml = `<html i="${textToTranslate[0]}" h="${textToTranslate[1]}" rme="${textToTranslate[4]}" add="${textToTranslate[5]}">\n${textToTranslate[3]}\n</html>`;

    if (showDebug) console.log(`textPart before replace:\n${textToTranslateHtml.slice(0, 100)}`);
    //console.log(`textPart before replace:\n${textToTranslateHtml}`);



    const textPartReplaceRegex = new RegExp(
      [
        `\\s*`, // space before
        `(?:`,
          // "symbols in square braces"
          // we use this pattern as placeholder for html tags and whitespace
          // so we have to escape existing strings with this pattern
          //`\\[[${codeNumRegexCharClassImport}]+\\]`,
          // verbose ascii code `ref${num}`;
          `\\[ref[${codeNumRegexCharClassImport}]+\\]`,
          `|`,
          //`\\n{2,}`, // extra newlines: needed for transliterated translations
          // replace all newlines
          // to google translate, newline means "new sentence"
          // so extra newlines break the context of words
          `\\n+`,
          `|`,
          // html tags
          // this will also replace the added <html> and </html> tags
          // TODO why do we add the <html> and </html> tags?
          `<.+?>`,
          `|`,
          // html entities
          // these can be long...
          // &CounterClockwiseContourIntegral;
          // https://stackoverflow.com/questions/12566098/what-are-the-longest-and-shortest-html-character-entity-names
          `&[^ ]{2,40};`,
        `)`,
        `\\s*` // space after
      ].join(''),
      'sgu'
    );

    //console.log(`textToTranslateHtml`, JSON.stringify(textToTranslateHtml)); // debug

    // encode html
    // replace html tags with "symbols in square braces"
    // consume all whitespace around the source text
    let textPart = textToTranslateHtml.replace(
      textPartReplaceRegex,
      match => getReplace(match)
    );

    const textPartRawList = [];
    let lastMatchEnd = 0;

    textToTranslateHtml.replace(
      textPartReplaceRegex,
      (match, matchPos) => {
        // add text before match
        const textBeforeMatch = (
          textToTranslateHtml.slice(lastMatchEnd, matchPos)
        );
        if (debugAlignment) {
          console.log(`textBeforeMatch`, JSON.stringify(textBeforeMatch));
        }
        if (textBeforeMatch != "") {
          textPartRawList.push([
            textBeforeMatch,
            0, // isReplacement
          ])
        }
        // see also: getReplace
        const replacementId = replacementData_lastId_2 + 1;
        if (debugAlignment) {
          console.log(`match`, JSON.stringify(match));
        }
        textPartRawList.push([
          match,
          1, // isReplacement
          replacementId,
        ])
        lastMatchEnd = matchPos + match.length;
        replacementData_lastId_2++;
      }
    );
    //console.dir({ textPartRawList }); throw new Error("todo");

    if (showDebug) console.log(`textPart after replace:\n${textPart.slice(0, 100)}`);
    //console.log(`textPart after replace:\n${textPart}`);

    // check 1: sourceText versus textPartRaw
    const textPartActual = stringifyRawTextGroup(textPartRawList);
    if (false) {
      console.log("textPartRawList", textPartRawList.slice(0, 10));
      console.log("textPart", textPart.slice(0, 100));
      console.log("textPartActual", textPartActual.slice(0, 100));
      throw new Error("todo")
    }
    if (textPart != textPartActual) {
      throw new Error(`FIXME textPart != textPartActual`)
    }

    const textLang = textToTranslate[2];

    if (!textPartsByLang[textLang]) {
      textPartsByLang[textLang] = [];
    }

    // textPart is a mix of text and codes
    // serialized into one string
    textPartsByLang[textLang].push(textPart);
    //textPartsByPos.push(textPart);

    if (!textPartRawListByLang[textLang]) {
      textPartRawListByLang[textLang] = [];
    }

    // textPartRawList is the same mix of text and codes
    // but splitted into an array of text-parts and codes
    textPartRawListByLang[textLang].push(textPartRawList);

  }
  // loop textToTranslateList done

  const replacementDataPath = inputPath + '.' + inputHtmlHash + '.replacementData.json';
  console.error(`writing ${replacementDataPath}`);
  fs.writeFileSync(replacementDataPath, JSON.stringify(replacementData, null, 2), "utf8");



  // build groups of text, limited by charLimit

  function stringifyRawTextGroup(textGroupRaw) {
    return textGroupRaw.map(part => {
      if (part[1] == 0) {
        // no replacement
        return part[0];
      }
      // else: part[1] == 1
      // replacement
      return ` [ref${part[2]}] `;
    }).join("");
  }

  function stringifyDecodedRawTextGroup(textGroupRaw) {
    return textGroupRaw.map(part => {
      return part[0];
    }).join("");
  }

  // note: this is just an approximation of the decoded html
  // because here, we dont restore whitespace
  // this decode is useful to see html tags
  function stringifyDecodedDecodedRawTextGroup(textGroupRaw) {
    return textGroupRaw.map(part => {
      if (part[1] == 0) {
        // no replacement
        return part[0];
      }
      // else: part[1] == 1
      // decode the replacement

      const replacementValue = part[0];

      if (!replacementValue.startsWith('<html ')) {
        return " ";
      }

      // parse text part index from replacementValue
      let [_match, textIdx, textHash, todoRemoveEndOfSentence, todoAddToTranslationsDatabase] =
        replacementValue.match(/<html i="([0-9]+)" h="([^"]*)" rme="([01])" add="([01])">/);

      if (textHash == "") {
        return " ";
      }
      textIdx = parseInt(textIdx);

      // TODO? use todoRemoveEndOfSentence
      // TODO? use todoAddToTranslationsDatabase

      // idx, sourceHash, sourceLang, sourceText
      //const textToTranslateSourceText = textToTranslateList[textIdx][3];

      const htmlBefore = htmlBetweenReplacementsList[textIdx];

      //console.dir({ htmlBefore, textIdx, replacementId, textToTranslateSourceText })

      if (htmlBefore == "") {
        return " ";
      }

      if (htmlBefore === undefined) {
        // FIXME more codes than textToTranslateList
        // because replacementId is sparse? how to get the index in textToTranslateList?
        // replacementId: 2649,
        // htmlBetweenReplacementsList_length: 2551,
        // textToTranslateList_length: 2550,
        // -> replacementId is index in replacementData.replacementList
        // -> there are two replacement passes, because legacy code
        console.dir({ htmlBefore, replacementId, replacementIdCode, codeStartIdx, replacementValue, htmlBetweenReplacementsList_length: htmlBetweenReplacementsList.length, textToTranslateList_length: textToTranslateList.length, lastGroup_start: lastGroup.slice(0, 100), lastGroup_end: lastGroup.slice(-100) })
        throw new Error(`FIXME more codes than textToTranslateList`);
      }

      return " " + htmlBefore + " ";
    }).join("");
  }

  const textGroupsByLang = {};
  const textGroupsRawBySourceLang = {};

  // loop textPartsByLang
  for (const sourceLang of Object.keys(textPartsByLang)) {

    // TODO where do we store all source text parts?
    const textParts = textPartsByLang[sourceLang];

    const textPartRawList = textPartRawListByLang[sourceLang];

    // TODO why?
    let lastGroupSize = 0;

    // reset state of decodeNum
    decodeNumOffest = 0;
    decodeNumLastResult = 0;

    // FIXME this is stupid...
    // TODO first build textGroupsRaw, then textGroups?

    const textGroups = [''];
    const textGroupsRaw = [[]];

    let thisGroupLength = 0;

    //const textGroups = (
    //  textParts.reduce((textGroups, sourceText) => {

    // loop textParts
    for (let textPartsIdx = 0; textPartsIdx < textParts.length; textPartsIdx++) {

      // TODO where do we store all source text parts?
      const sourceText = textParts[textPartsIdx];

      const textPartRaw = textPartRawList[textPartsIdx];

      //console.dir({ sourceText, textPartRaw });

      // check 2: sourceText versus textPartRaw
      // TODO remove?
      const sourceTextActual = stringifyRawTextGroup(textPartRaw);
      if (sourceTextActual != sourceText) {
        console.dir({ sourceTextActual, sourceText });
        throw new Error(`FIXME sourceTextActual != sourceText`)
      }

      // filter textPart
      // TODO where do we store all source text parts?
      // groups.json and textGroupsRawByLang.json have filtered text parts
      const textPartHash = sourceLang + ':' + targetLang + ':' + sha1sum(sourceText);
      if (textPartHash in translationsDatabase) {
        // translation exists in local database
        // TODO why do we reach this so rarely?
        // most text parts are still sent to the translator
        // maybe we sourceText contains dynamic strings (replacement codes)
        //return textGroups;
        continue;
      }
      // TODO why `\n\n<meta attrrrrrrrr="vallll"/>\n\n`
      // sure, the purpose is to make sure
      // that the text group is smaller than charLimit
      // but why do we have to round the length here?
      //const nextLen = acc[acc.length - 1].length + sourceText.length + 3*(`\n\n<meta attrrrrrrrr="vallll"/>\n\n`.length);
      //const nextLen = textGroups[textGroups.length - 1].length + sourceText.length;
      const thisGroupLengthNext = thisGroupLength + sourceText.length;

      // TODO remove
      const thisGroupString = stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 1]);
      const thisGroupLengthExpected = thisGroupString.length;
      if (thisGroupLength != thisGroupLengthExpected) {
        console.dir({ thisGroupLength, thisGroupLengthExpected, thisGroupLengthNext, thisGroupString })
        throw new Error("thisGroupLengthExpected != thisGroupLengthExpected");
      }

      // start a new group, move the too-much text-parts to the next group
      if (thisGroupLengthNext >= charLimit) {

        false &&
        console.dir({ thisGroupLengthNext, charLimit });

        textGroups.push(''); // TODO remove
        textGroupsRaw.push([]);
        lastGroupSize = 0; // TODO remove?
        const thisGroup = textGroups[textGroups.length - 1];
        const lastGroup = textGroups[textGroups.length - 2];
        const thisGroupRaw = textGroupsRaw[textGroupsRaw.length - 1];
        const lastGroupRaw = textGroupsRaw[textGroupsRaw.length - 2];
        //const thisGroup = acc[acc.length - 1];
        // dont break sentences across groups
        // move the end of the last group to the new group
        // loop replacements, find the first "<div" or "<h3" or "<h2"

        let lastGroupEndGroupIdx = null;

        // TODO check last items of last group
        // maybe preserve the last group
        // TODO also look for closing tags? </div> </h1> etc
        // TODO get htmlBefore

        // loop items of last group
        // TODO better? when adding text-parts to this group
        // look for "start of last paragraph or heading"
        // and keep track of that position
        // if the current group grows too large
        // then move the too-much text-parts to the next group
        // but in theory, this is less efficient
        // because we have to analyze more text-parts
        for (let lastGroupRawIdx = lastGroupRaw.length - 1; lastGroupRawIdx > 0; lastGroupRawIdx--) {
          const lastGroupRawItem = lastGroupRaw[lastGroupRawIdx];
          //console.dir({ lastGroupRawItem });
          if (lastGroupRawItem[1] == 0) {
            // text node
            // old code. this would analyze only html nodes
            // to find "end of sentence"
            // but this fails on large inline texts
            // so we also look for "end of sentence" in text nodes
            //continue;
            const textNodeContent = lastGroupRawItem[0];
            if (
              textNodeContent.endsWith(".") &&
              textNodeContent.match(/[a-zA-Z]{5,}\.$/s) !== null
            ) {
              false &&
              console.dir({ what: `found "end of sentence" in this text node`, textNodeContent });
              // found "end of sentence" in this text node
              // TODO off by one?
              lastGroupEndGroupIdx = lastGroupRawIdx;
              //lastGroupEndGroupIdx = lastGroupRawIdx + 1;
              break;
            }
            // not found "end of sentence" in this text node
            continue;
          }
          // lastGroupRawItem[1] != 0
          const replacementId = lastGroupRawItem[2];
          const replacementValue = lastGroupRawItem[0];
          //console.dir({ replacementValue });

          //throw new Error("todo");

          if (!replacementValue.startsWith('<html ')) {
            continue;
          }

          //console.log("replacementValue", replacementValue)

          // parse text part index from replacementValue
          let [_match, textIdx, _textHash, todoRemoveEndOfSentence, todoAddToTranslationsDatabase] =
            replacementValue.match(/<html i="([0-9]+)" h="([^"]*)" rme="([01])" add="([01])">/);

          textIdx = parseInt(textIdx);

          // TODO? use todoRemoveEndOfSentence

          // idx, sourceHash, sourceLang, sourceText
          //const textToTranslateSourceText = textToTranslateList[textIdx][3];

          const htmlBefore = htmlBetweenReplacementsList[textIdx];

          //console.dir({ htmlBefore, textIdx, replacementId, textToTranslateSourceText })

          if (htmlBefore === undefined) {
            // FIXME more codes than textToTranslateList
            // because replacementId is sparse? how to get the index in textToTranslateList?
            // replacementId: 2649,
            // htmlBetweenReplacementsList_length: 2551,
            // textToTranslateList_length: 2550,
            // -> replacementId is index in replacementData.replacementList
            // -> there are two replacement passes, because legacy code
            console.dir({ htmlBefore, replacementId, replacementIdCode, codeStartIdx, replacementValue: replacementValue, htmlBetweenReplacementsList_length: htmlBetweenReplacementsList.length, textToTranslateList_length: textToTranslateList.length, lastGroup_start: lastGroup.slice(0, 100), lastGroup_end: lastGroup.slice(-100) })
            throw new Error(`FIXME more codes than textToTranslateList`);
          }

          if (htmlBefore == "") {
            continue;
          }

          // parse last html tag
          const lastTagStart = htmlBefore.lastIndexOf("<");
          const lastTag = htmlBefore.slice(lastTagStart);
          //if (lastTag.match(/<div(\s|\s+.*\s+)class="(\s*|[^"]+\s+)(annotation)(\s*|\s+[^"]+)"/s))
          // htmlBefore is verbose
          if (lastTag == "") {
            console.dir({ lastTag, htmlBefore });
            continue;
          }
          if (
            // see also: isSentenceTag
            //lastTag.match(/^<(title|h[1-9]|div|li|td)/s) != null ||
            lastTag.match(/^<\/?(title|h[1-9]|div|li|td)/s) != null || // also match close-tags
            // no. assume that all <div> are block elements
            // so inline elements must be <span> for example <span class="note">
            //lastTag.match(/^<div(\s|\s+.*\s+)class="(\s*|[^"]+\s+)(para)(\s*|\s+[^"]+)"/s) != null ||
            false
          ) {

            false &&
            console.dir({ lastGroupRawIdx, replacementValue, lastTag, isSentenceStartTag: true });

            // start of last paragraph or heading
            //const lastGroupEnd = codeEndIdx; // TODO?
            //lastGroupEnd = codeEndIdx + 1;

            lastGroupEndGroupIdx = lastGroupRawIdx;

            //console.dir({ lastTag, lastGroupRawIdx }); // debug
            break;
          }
          else {
            false &&
            console.dir({ lastGroupRawIdx, replacementValue, lastTag, isSentenceStartTag: false });
          }
          //counter++; if (counter > 20) process.exit(1); // debug

        } // loop items of last group

        if (lastGroupEndGroupIdx !== null) {

          // stats
          const lastGroupSizeBefore = stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 2]).length;
          const thisGroupSizeBefore = stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 1]).length;

          // add text-parts to this group
          if (textGroupsRaw[textGroupsRaw.length - 1].length == 0) {
            //textGroupsRaw[textGroupsRaw.length - 1] = textGroupsRaw[textGroupsRaw.length - 2].slice(lastGroupEndGroupIdx);
            textGroupsRaw[textGroupsRaw.length - 1] = textGroupsRaw[textGroupsRaw.length - 2].slice(lastGroupEndGroupIdx + 1);
          }
          else {
            // TODO remove?
            // TODO is this never reached?
            throw new Error("TODO keep this branch");
            //textGroupsRaw[textGroupsRaw.length - 1].push(...textGroupsRaw[textGroupsRaw.length - 2].slice(lastGroupEndGroupIdx));
            textGroupsRaw[textGroupsRaw.length - 1].push(...textGroupsRaw[textGroupsRaw.length - 2].slice(lastGroupEndGroupIdx + 1));
          }

          // remove text-parts from last group
          //textGroupsRaw[textGroupsRaw.length - 2] = textGroupsRaw[textGroupsRaw.length - 2].slice(0, lastGroupEndGroupIdx);
          textGroupsRaw[textGroupsRaw.length - 2] = (
            textGroupsRaw[textGroupsRaw.length - 2].slice(0, lastGroupEndGroupIdx + 1)
          );

          // stats
          const lastGroupSizeAfter = stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 2]).length;
          const thisGroupSizeAfter = stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 1]).length;

          // update group length of this group
          const thisGroupLengthBefore = thisGroupLength;
          thisGroupLength = stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 1]).length;
          false && console.dir({
            thisGroupLength,
            thisGroupLengthBefore,
            lastGroupSizeBefore,
            lastGroupSizeAfter,
            thisGroupSizeBefore,
            thisGroupSizeAfter,
          });

          false &&
          console.dir({
            what: "moved items from last group to this group",
            lastGroupEnd: textGroupsRaw[textGroupsRaw.length - 2].slice(-5),
            thisGroupStart: textGroupsRaw[textGroupsRaw.length - 1].slice(0, 5),
          });
          //throw new Error("TODO verify");

          /*
          console.dir({ what: "moving from last group to this group", lastGroupEnd, moveText: lastGroup.slice(lastGroupEnd), moveTextCount });
          //process.exit(1); // debug
          textGroups[textGroups.length - 1] += lastGroup.slice(lastGroupEnd);
          textGroups[textGroups.length - 2] = lastGroup.slice(0, lastGroupEnd);

          // FIXME off by one errors?
          const groupRaw = textGroupsRaw[textGroupsRaw.length - 1];
          for (let i = lastGroupRaw.length - moveTextCount; i < lastGroupRaw.length; i++) {
            console.log(`moving raw group`, lastGroupRaw[i]);
            groupRaw.push(lastGroupRaw[i]);
          }
          textGroupsRaw[textGroupsRaw.length - 2] = lastGroupRaw.slice(0, lastGroupRaw.length - moveTextCount);

          console.dir({ 'group start': textGroups[textGroups.length - 1].slice(0, 100) });
          console.dir({ 'groupRaw start': groupRaw.slice(0, 3) });

          console.dir({ 'lastGroup end': textGroups[textGroups.length - 2].slice(-100) });
          console.dir({ 'lastGroupRaw end': textGroupsRaw[textGroupsRaw.length - 2].slice(-3) });
          */

          //throw new Error("TODO move items from last group to this group");
        }

        // else: lastGroupEndGroupIdx === null
        else {
          //throw new Error("FIXME lastGroupEndGroupIdx === null");
          console.log(`warning: not moving text-parts of large group ${textGroupsRaw.length - 2} with length ${stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 2]).length}`);
          console.log(`group ${textGroupsRaw.length - 2}:`);
          console.log(`--------------------------------------------------------------------------------`);
          // TODO decode replacements
          //console.log(stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 2]));
          console.log(stringifyDecodedDecodedRawTextGroup(textGroupsRaw[textGroupsRaw.length - 2]));
          console.log(`--------------------------------------------------------------------------------`);

          // TODO remove? thisGroup was not modified
          // update group length of this group
          const thisGroupLengthBefore = thisGroupLength;
          thisGroupLength = stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 1]).length;
          false &&
          console.dir({ thisGroupLength, thisGroupLengthBefore });
          if (thisGroupLength != thisGroupLengthBefore) {
            throw new Error("thisGroupLength != thisGroupLengthBefore");
          }
        }

      } // start a new group

      // else: thisGroupLengthNext < charLimit
      /*
      else {
        const thisGroupLengthBefore = thisGroupLength;
        thisGroupLength = thisGroupLengthNext;
        console.dir({ thisGroupLength, thisGroupLengthBefore });

        // TODO remove
        const thisGroupString = stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 1]);
        const thisGroupLengthExpected = thisGroupString.length;
        if (thisGroupLength != thisGroupLengthExpected) {
          console.dir({ thisGroupLength, thisGroupLengthExpected, thisGroupLengthNext, thisGroupString })
          throw new Error("thisGroupLengthExpected != thisGroupLengthExpected");
        }
      }
      */

      // add textPart to textGroup
      // dont add newlines
      //acc[acc.length - 1] += sourceText + '\n\n';
      //textGroups[textGroups.length - 1] += sourceText; // TODO remove

      // TODO same format is in groups.json
      // TODO where are our codes? [ref...]
      //const todoRemoveEndOfSentence = 0; // TODO
      // no. sourceText is the escaped text with [ref...] codes
      // fix: use  textPartRaw
      //textGroupsRaw[textGroupsRaw.length - 1].push([textPartsIdx, textPartHash, sourceLang, sourceText, todoRemoveEndOfSentence]);
      textGroupsRaw[textGroupsRaw.length - 1].push(...textPartRaw);

      lastGroupSize++; // TODO remove?

      thisGroupLength += sourceText.length;

      // TODO remove
      if (0) {
        const thisGroupString = stringifyRawTextGroup(textGroupsRaw[textGroupsRaw.length - 1]);
        const thisGroupLengthExpected = thisGroupString.length;
        if (thisGroupLength != thisGroupLengthExpected) {
          console.dir({ thisGroupLength, thisGroupLengthExpected, thisGroupLengthNext, thisGroupString })
          throw new Error("thisGroupLengthExpected != thisGroupLengthExpected");
        }
      }

      //return textGroups;
      //}, [''])

      /* DEBUG is this broken?
      // group siblings
      .map(textGroup => textGroup.replace(/\n(?:\[[\d ]+\]\s*){2,}\n/sg, matchStr => {
        const replaceIdList = [];
        // preserve extra whitespace between replacements
        matchStr.replace(/(\s*)\n\[([\d ]+)\]\n(\s*)/g, (_, spaceBefore, idStr, spaceAfter) => {
          const replaceId = parseInt(idStr.replace(/ /g, ''));
          if (0 && showDebug) console.dir({ replaceId }); // verbose
          replacementList[replaceId] = (
            spaceBefore + replacementList[replaceId] + spaceAfter
          );
          replaceIdList.push(replaceId);
        });
        if (0 && showDebug) console.dir({ matchStr, replaceIdList }); // verbose
        const firstId = replaceIdList.shift();
        // move all replacements to firstId
        for (const replaceId of replaceIdList) {
          replacementList[firstId] += replacementList[replaceId];
          replacementList[replaceId] = '';
        }
        return `\n[${fmtNum(firstId)}]\n`;
      }))
      */
    //);

    } // loop textParts end

    // TODO what?
    const textGroups__newCode = textGroupsRaw.map(textPartRaw => textPartRaw.map(part => {
      if (part[1] == 0) {
        // no replacement
        return part[0];
      }
      // else: part[1] == 1
      // replacement
      return ` [ref${part[2]}] `;
    }).join(""));

    /*
    // TODO remove
    // textGroups is not set any more
    for (let i = 0; i < textGroups__newCode.length; i++) {
      const sourceText = textGroups[i];
      const sourceTextActual = textGroups__newCode[i];
      if (sourceTextActual != sourceText) {
        console.dir({ sourceTextActual, sourceText });
        throw new Error(`FIXME sourceTextActual != sourceText`)
      }
    }
    */

    //textGroupsByLang[sourceLang] = textGroups;
    textGroupsRawBySourceLang[sourceLang] = textGroupsRaw;

    textGroupsByLang[sourceLang] = textGroups__newCode;

    if (showDebug) {
      //console.log(textGroups.map((s, i) => `textGroup ${sourceLang} ${i}:\n${s}\n`).join('\n'));
      console.log(textGroups__newCode.map((s, i) => `textGroup ${sourceLang} ${i}:\n${s}\n`).join('\n'));
    }

  }
  // loop textPartsByLang done

  const textPartsByLangPath = inputPath + '.' + inputHtmlHash + '.textPartsByLang.json';
  console.error(`writing ${textPartsByLangPath}`);
  fs.writeFileSync(textPartsByLangPath, JSON.stringify(textPartsByLang, null, 2), "utf8");

  // TODO rename to filtered-groups
  // TODO rename to filtered-groups-raw
  // "filtered" as in: these files do not contain texts
  // which are already in the translations database
  // so we dont send them to the translator again

  const textGroupsPath = inputPath + '.' + inputHtmlHash + '.textGroupsByLang.json';
  console.error(`writing ${textGroupsPath}`);
  fs.writeFileSync(textGroupsPath, JSON.stringify(textGroupsByLang, null, 2), "utf8");

  const textGroupsRawByLangPath = inputPath + '.' + inputHtmlHash + '.textGroupsRawByLang.json';
  console.error(`writing ${textGroupsRawByLangPath}`);
  fs.writeFileSync(textGroupsRawByLangPath, JSON.stringify(textGroupsRawBySourceLang, null, 2), "utf8");



  //return;



  // finally... send the text groups to the translation service
  // FIXME this can fail, then we have to retry
  // so write finished translations to a local database (json? sql?)



  // no. the LingvaScraper client fails most times
  /*
  for (const sourceLang of Object.keys(textGroupsByLang)) {
    const textGroups = textGroupsByLang[sourceLang];
    for (const textGroup of textGroups) {
      // TODO get "sha1sum(textGroup)" without our markers "[*>-]" etc
      // the markers can change between runs
      // TODO store smaller parts of the translation
      const textGroupHash = sourceLang + ':' + targetLang + ':' + sha1sum(textGroup);
      if (textGroupHash in doneTranslations) {
        // translation exists in local database
        continue;
      }
      // get translation
      console.log(`translating textGroup: ${textGroup}`);
      const translation = await LingvaScraper.getTranslationText(sourceLang, targetLang, textGroup);
      // TODO what is (translation == null)? error?
      console.log(`translation: ${translation}`);
      doneTranslations[textGroupHash] = [textGroup, translation];
      // write database
      // "write early, write often" to avoid data loss on error
      // downside: the hard drive will suffer from more write cycles
      console.log(`writing ${translationsDatabaseJsonPath}`);
      fs.writeFileSync(translationsDatabaseJsonPath, JSON.stringify(doneTranslations, null, 2), "utf8");
      await sleep(sleepBetweenTranslationRequests);
    }
  }
  */



  function joinText(text) {
    return text.replace(/( ?\[ref[0-9]+\] ?)+/g, " ");
  }

  function splitText(text) {
    // translators interpret "\n" as "end of sentence"
    return text.replace(/( ?\[ref[0-9]+\] ?)+/g, "\n");
  }

  // generate links

  const translateLinks = [];
  for (const sourceLang of Object.keys(textGroupsByLang)) {
    if (sourceLang == targetLang) {
      continue;
    }
    //for (const textGroupRaw of textGroupsByLang[sourceLang]) {
    for (let textGroupRawIdx = 0; textGroupRawIdx < textGroupsByLang[sourceLang].length; textGroupRawIdx++) {
      const textGroupRaw = textGroupsByLang[sourceLang][textGroupRawIdx];
      // sorted by alphabet: joined, splitted
      for (const exportFn of [joinText, splitText]) {
        const textGroup = exportFn(textGroupRaw);
        const translateUrl = (
          translatorName == 'google' ? `https://translate.google.com/?op=translate&sl=${sourceLang}&tl=${targetLang}&text=${encodeURIComponent(textGroup)}` :
          translatorName == 'deepl' ? `https://www.deepl.com/translator#${sourceLang}/${targetLang}/${encodeURIComponent(deeplBackslashEncode(textGroup))}` :
          '#invalid-translatorName'
        );
        const previewText = (
          htmlEntities.encode(textGroup.slice(0, previewTextLength/2)) + ' ... ' +
          htmlEntities.encode(textGroup.slice(-previewTextLength/2))
        ).replace(/\n/sg, " ");
        // see also translationsBaseNameMatch
        const linkId = `translation-${sourceLang}-${targetLang}-${textGroupRawIdx.toString().padStart(4, '0')}` + (
          (exportFn == joinText) ? "-joined" :
          (exportFn == splitText) ? "-splitted" :
          ""
        );
        translateLinks.push(`<div id="group-${linkId}">group ${linkId}: <a target="_blank" href="${translateUrl}">${sourceLang}:${targetLang}: ${previewText}</a></div>\n`);
      }
    }
  }

  const htmlSrc = (
    '<style>' +
      'a:visited { color: green; }' +
      'a { text-decoration: none; }' +
      'a:hover { text-decoration: underline; }' +
      'div { margin-bottom: 1em; }' +
    '</style>\n' +
    '<div id="groups">\n' + translateLinks.join('') + '</div>\n' +
    /*
    // embed replacements in html comment
    '<!-- replacementData = ' +
    JSON.stringify(replacementData, null, 2) +
    ' = replacementData -->' +
    */
    ''
  );

  const translateLinksPath = inputPath + '.' + inputHtmlHash + `.translate-${targetLang}.html`;

  console.log(`writing ${translateLinksPath}`);
  fs.writeFileSync(translateLinksPath, htmlSrc, 'utf8');
  const translateLinksPathUrl = encodeURI('file://' + path.resolve(translateLinksPath));

  const scriptPath = "translate-richtext.js";

  // TODO update
  console.log(`
next steps:

1. open the translate html file in your browser:
   xdg-open ${translateLinksPathUrl}
2. click the first link
3. fix the translation on the translator website,
   so the translator can learn to translate better
4. scroll down, on the bottom right, click on: copy translation
5. paste the translation to your text editor
   remove the footers:
   Translated with www.DeepL.com/Translator (free version)
5a. or write each translated block to a separate file:
   n=1
   o=translate-done-${targetLang}.$n.txt; xclip -sel c -o >"$o"; echo done "$o"; n=$((n + 1))
   o=translate-done-${targetLang}.$n.txt; xclip -sel c -o >"$o"; echo done "$o"; n=$((n + 1))
   o=translate-done-${targetLang}.$n.txt; xclip -sel c -o >"$o"; echo done "$o"; n=$((n + 1))
   ...
   until n == ${translateLinks.length}
   and then concat all these text files into one text file:
   for n in $(seq ${translateLinks.length}); do cat translate-done-${targetLang}.$n.txt; done >translate-done-${targetLang}.txt
6. repeat for all links (append translations to text file)
7. save the text file, for example as translate-done-${targetLang}.txt
8. run this script again with the text file, for example:
node ${scriptPath} ${targetLang} translate-done-${targetLang}.txt

note:
translators will change the order of words,
so in some cases, html markup tags like <b>....</b>
will be in a wrong position.

note:
the ${translateLinksPath} file is valid only for one iteration.
if you added nodes to the html files,
then you must generate a new ${translateLinksPath} file
`)



}



const translatorLangs = {
  deepl: [
    // 2021-05-25
    'bg', 'zh', 'cs', 'da', 'nl', 'et', 'fi', 'fr', 'de', 'el', 'hu', 'it', 'ja',
    'lv', 'lt', 'pl', 'pt', 'pt-PT', 'pt-BR', 'ro', 'ru', 'sk', 'sl', 'es', 'sv'
  ],
};



// https://github.com/iansan5653/unraw/issues/29
// deepl.com:
//   / -> \/
//   \ -> \\
function deeplBackslashEncode(str) {
  let res = '';
  for (let i = 0; i < str.length; i++) {
    const char16bit = str[i];
    const code = char16bit.charCodeAt(0);
    res += (
      (code == 47) ? '\\/' : // forward slash
      (code == 92) ? '\\\\' : // backslash
      char16bit
    );
  }
  return res;
}

function dateTime(date = null) {
  // sample result: '2021-03-21.21-05-36'
  if (!date) date = new Date();
  return date.toLocaleString('lt').replace(/:/g, '-').replace(' ', '.');
}

const nowDate = dateTime();

function sha1sum(str) {
  //return crypto.createHash("sha1").update(str).digest("base64");
  return crypto.createHash("sha1").update(str).digest("hex");
}

// google can translate -- to -
// so we use "safe" ids without repetition
function getNextSafeId(lastId) {
  for (let id = (lastId + 1); ; id++) {
    let idStr = id.toString();
    let idSafe = true;
    for (let charIdx = 0; charIdx < (idStr.length - 1); charIdx++) {
      if (idStr[charIdx] == idStr[charIdx + 1]) {
        // found repetition
        idSafe = false;
        //if (showDebug) console.log(`skip unsafe id ${id}`);
        break;
      }
    }
    if (idSafe) return id;
  }
}



const wordRegex = /[^\s.,!?"]+/sg;

function getWordList(string) {
  // word.replace: remove trailing punctuations like "." or ","
  //return string.trim().split(/\s+/).map(word => word.replace(/[.,!?-]$/, ""));
  const wordList = [];
  string.replace(wordRegex, (word, wordPos) => {
    wordList.push([word, wordPos]);
    return "";
  });
  return wordList;
}

function replaceWords(string, func) {
  return string.replace(wordRegex, func);
}



/////////////////////// import ////////////////////////////

//async function importLang(sourceLang, targetLang, inputFile) {
async function importLang(inputPath, targetLang, translationsPathList) {

  console.log(`reading ${inputPath}`);
  const inputHtml = fs.readFileSync(inputPath, 'utf8');
  const inputHtmlHash = 'sha1-' + sha1sum(inputHtml);

  const inputPathFrozen = inputPath + '.' + inputHtmlHash;
  const outputTemplateHtmlPath = inputPathFrozen + '.outputTemplate.html';
  const textToTranslateListPath = inputPathFrozen + '.textToTranslateList.json';
  const replacementDataPath = inputPathFrozen + '.replacementData.json';
  const textGroupsPath = inputPathFrozen + '.textGroupsByLang.json';
  const textGroupsRawByLangPath = inputPathFrozen + '.textGroupsRawByLang.json';
  const htmlBetweenReplacementsPath = inputPathFrozen + '.htmlBetweenReplacementsList.json';
  const textPartsByLangPath = inputPathFrozen + '.textPartsByLang.json';

  const translatedHtmlPath = inputPathFrozen + `.translated-${targetLang}.html`;
  const translatedSplittedHtmlPath = inputPathFrozen + `.translated-${targetLang}.splitted.html`;

  //const translatedTextPath = inputPathFrozen + '.translated.txt';

  // local translations database. this file can be missing
  //const translationsDatabaseJsonPath = 'translations-database.json';

  // TODO add sourceLang and targetLang to the file name
  //const translationsDatabaseHtmlPath = 'translations-database.html';
  //const translationsDatabaseHtmlPathGlob = 'translations-database-*.html';
  const translationsDatabaseHtmlPathGlob = 'translations-google-database-*-*.html';

  const translationsDatabase = {};

  for (const translationsDatabaseHtmlPath of glob.sync(translationsDatabaseHtmlPathGlob)) {
    console.log(`reading ${translationsDatabaseHtmlPath}`)
    const sizeBefore = Object.keys(translationsDatabase).length;
    parseTranslationsDatabase(translationsDatabase, fs.readFileSync(translationsDatabaseHtmlPath, 'utf8'));
    const sizeAfter = Object.keys(translationsDatabase).length;
    console.log(`loaded ${sizeAfter - sizeBefore} translations from ${translationsDatabaseHtmlPath}`)
  }

  const inputPathList = [
    inputPathFrozen,
    outputTemplateHtmlPath,
    textToTranslateListPath,
    replacementDataPath,
    textGroupsPath,
    textGroupsRawByLangPath,
    textPartsByLangPath,
    ...translationsPathList,
  ]


  const outputPathList = [
    translatedHtmlPath,
    translatedSplittedHtmlPath,
  ]

  for (const path of outputPathList) {
    if (fs.existsSync(path)) {
      console.error(`error: output file exists: ${path}`);
      console.error(`hint:`);
      console.error(`  rm ${path}`);
      return 1;
    }
  }

  for (const path of inputPathList) {
    if (!fs.existsSync(path)) {
      console.error(`error: missing input file: ${path}`);
      console.error(
        'hint: run this script again without the last argument ' +
        '(translations.txt) to rebuild the input files. ' +
        'before that, maybe backup your old input files'
      );
      return 1;
    }
  }

  if (translationsPathList.length % 2 != 0) {
    const lastFile = translationsPathList.pop();
    console.log(`warning: expecting an even number of translation.txt files in pairs of "joined" and "splitted" translations. ignoring the last file: ${lastFile}`);
  }

  // read textGroupsRaw.json
  console.log(`reading ${textGroupsRawByLangPath}`);
  const textGroupsRawBySourceLang = JSON.parse(fs.readFileSync(textGroupsRawByLangPath, 'utf8'));

  // read textToTranslateList.json
  console.log(`reading ${textToTranslateListPath}`);
  const textToTranslateList = JSON.parse(fs.readFileSync(textToTranslateListPath, 'utf8'));

  translationsPathList.sort();

  // read html-chunks.json
  console.log(`reading ${htmlBetweenReplacementsPath}`);
  const htmlBetweenReplacementsList = JSON.parse(fs.readFileSync(htmlBetweenReplacementsPath, 'utf8'));
  let htmlBetweenReplacementsIdx = 0;

  // build list of text parts: source text + translations
  //const translatedTextLineListByInputFileList = [];

  console.log(`reading ${translationsPathList.length} input files`);

  // TODO rename textGroupRawParsedList to textBlockList
  const textGroupRawParsedList = [];

  let textGroupRawParsed = null;
  let textGroupRawParsedIdxLast = 0;
  let textBlockTextPartIdxNext = 0;
  let textBlockTextPartIdxNextLast = 0;

  console.log(`populating textGroupRawParsedList ...`);

  // loop input files: add source and translated text parts to textGroupRawParsed
  for (let translatedFileId = 0; translatedFileId < translationsPathList.length / 2; translatedFileId++) {

    debugAlignment &&
    console.log(`translatedFileId ${String(translatedFileId).padStart(5)}`);

    // TODO get sourceLang of this translation
    // TODO google-translate.sh: add sourceLang to output filenames

    // this indexing is based on the sort order
    // 00-joined
    // 00-splitted
    // 01-joined
    // 01-splitted

    const joinedTranslationsPath = translationsPathList[translatedFileId * 2];
    const splittedTranslationsPath = translationsPathList[translatedFileId * 2 + 1];

    // debug
    // FIXME translatedTextLineCombinedJoinedSplitted == undefined
    if (false && debugAlignment && translatedFileId >= 84) {
      console.log(`translatedFileId ${translatedFileId}`);
      console.log(`joinedTranslationsPath ${joinedTranslationsPath}`);
      console.log(`splittedTranslationsPath ${splittedTranslationsPath}`);
      console.log(`textGroupRawParsedIdxLast ${textGroupRawParsedIdxLast}`);
    }

    if (!joinedTranslationsPath.endsWith("-joined.txt")) {
      throw new Error(`error: not found the '-joined.txt' suffix in joinedTranslationsPath: ${joinedTranslationsPath}`);
    }
    if (!splittedTranslationsPath.endsWith("-splitted.txt")) {
      throw new Error(`error: not found the '-splitted.txt' suffix in splittedTranslationsPath: ${splittedTranslationsPath}`);
    }

    const translationsBasePath = joinedTranslationsPath.slice(0, -1 * "-joined.txt".length);
    const splittedTranslationsBasePath = splittedTranslationsPath.slice(0, -1 * "-splitted.txt".length);
    if (translationsBasePath != splittedTranslationsBasePath) {
      console.dir({ translationsBasePath, splittedTranslationsBasePath });
      throw new Error("joinedTranslationsBasePath != splittedTranslationsBasePath");
    }

    // example: xxx.translation-de-en-0001
    const translationsBaseName = path.basename(translationsBasePath);
    const translationsBaseNameMatch = translationsBaseName.match(/\.translation-([a-z_]+)-([a-z_]+)-([0-9]{4})$/);
    if (translationsBaseNameMatch == null) {
      throw new Error(`failed to parse translationsBaseName: ${translationsBaseName}`);
    }
    const [sourceLang, targetLang, translationFileIdxStr] = translationsBaseNameMatch.slice(1);
    const translationFileIdx = parseInt(translationFileIdxStr);
    //console.dir({ sourceLang, targetLang, translationFileIdx });

    // TODO rename textGroupRawList to textPartNodeList
    const textGroupRawList = textGroupsRawBySourceLang[sourceLang][translationFileIdx];

    // moved up
    //const textGroupRawParsedList = [];
    //let textBlockIdx = -1;

    const debugTextGroupRawParser = false;

    // add values to textGroupRawParsed.textBlockTextPartList
    // parse text groups = source text blocks
    // each source text block is identified by its sourceTextBlockHash
    // TODO rename textGroupRaw to textPartNode
    for (const textGroupRaw of textGroupRawList) {
      //console.dir({ textBlockIdx, textGroupRaw });
      if (debugTextGroupRawParser) {
        console.dir({ L: 2900, textGroupRaw });
      }
      if (textGroupRaw[1] == 1) {
        // replacement: <html> or </html> or whitespace (or other html code?)
        if (textGroupRaw[0].startsWith('<html ')) {
          // start of block
          //console.dir({ textGroupRaw_0: textGroupRaw[0] });
          let [
            _match, sourceTextBlockIdx, sourceTextBlockHash, todoRemoveEndOfSentence,
            todoAddToTranslationsDatabase, whitespaceBeforeFirstTextPart
          ] = textGroupRaw[0].match(/^<html i="([0-9]+)" h="([^"]*)" rme="([01])" add="([01])">\n(.*)$/s);

          sourceTextBlockIdx = parseInt(sourceTextBlockIdx);
          todoRemoveEndOfSentence = parseInt(todoRemoveEndOfSentence);
          todoAddToTranslationsDatabase = parseInt(todoAddToTranslationsDatabase);

          if (sourceTextBlockHash == "") {
            //console.dir({ textGroupRaw }); throw Error("TODO handle empty sourceTextBlockHash");
          }
          if (todoRemoveEndOfSentence == 1) {
            //console.dir({ textGroupRaw }); throw Error("TODO handle todoRemoveEndOfSentence == 1");
          }

          const textGroupRawParsedNew = {
            translatedFileId,
            sourceTextBlockIdx,
            sourceTextBlockHash,
            //sourceTextBlockText: "",
            // TODO better? merge all text arrays?
            // textPartList = [ [a0, a1, a2], [b0, b1, b2] ]
            // a0, b0, ... are the source text parts
            // a1, b1, ... are the translated text parts of translation 1
            // a2, b2, ... are the translated text parts of translation 2
            // textPartNode = { isWhitespace: true, content: "\n  " }
            // textPartNode = { isWhitespace: false, content: "asdf" }
            textBlockTextPartList: [
              whitespaceBeforeFirstTextPart,
            ],
            textBlockTextPartIsTextList: [
              // true = this part is text: source text and translated texts
              // false = this part is whitespace
              false,
            ],
            todoRemoveEndOfSentence,
            todoAddToTranslationsDatabase,
            translations: {},
            /*
            translations: {
              // TODO rename "LineList" to "PartList"
              splittedTranslationLineList: [
                whitespaceBeforeFirstTextPart,
              ],
              joinedTranslationLineList: [
                whitespaceBeforeFirstTextPart,
              ],
            },
            */
          };

          textGroupRawParsedList.push(textGroupRawParsedNew);
          textGroupRawParsed = textGroupRawParsedNew;

          // TODO add more translations
          for (const translationName of ["splitted", "joined"]) {
            // TODO rename "LineList" to "PartList"
            const key = `${translationName}TranslationLineList`;
            textGroupRawParsed.translations[key] = [
              // TODO later: add whitespace to translations
              //whitespaceBeforeFirstTextPart,
            ];
          }
        }
        else if (textGroupRaw[0].endsWith("\n</html>")) {
          // end of block
          // TODO handle todoRemoveEndOfSentence == 1 (here?)
          // 8 == "\n</html>".length
          const whitespaceAfterLastTextPart = textGroupRaw[0].slice(0, -8);
          if (debugTextGroupRawParser) {
            console.dir({ L: 2980, textGroupRaw, whitespaceAfterLastTextPart })
          }
          textGroupRawParsed.textBlockTextPartList.push(whitespaceAfterLastTextPart);
          textGroupRawParsed.textBlockTextPartIsTextList.push(false);
          // TODO later: add whitespace to translations
          /*
          // TODO rename "LineList" to "PartList"
          for (const translationLineList of Object.values(textGroupRawParsed.translations)) {
            translationLineList.push(whitespaceAfterLastTextPart);
          }
          */
          if (textGroupRawParsed.todoRemoveEndOfSentence == 1) {
            const textBlockTextPartList = textGroupRawParsed.textBlockTextPartList;
            let idx = textBlockTextPartList.length - 1;
            if (whitespaceAfterLastTextPart == "") {
              // "." is in previous text part. TODO why? this was working before...
              idx = idx - 1;
            }
            if (debugAlignment) {
              console.log(`3000 textBlockTextPartList[idx] ${JSON.stringify(textBlockTextPartList[idx])}`)
            }
            const end = textBlockTextPartList[idx].slice(-1);
            if (end != ".") {
              console.dir({ L: 2990, textGroupRaw, textBlockTextPartList_idx: textBlockTextPartList[idx] });
              throw new Error(`unexpected end: ${JSON.stringify(end)}`);
            }
            // remove last char
            textBlockTextPartList[idx] = textBlockTextPartList[idx].slice(0, -1);
          }
          //textBlockIdx = -1;
          textGroupRawParsed = null;
        }
        else {
          if (textGroupRaw[0].match(/^\s+$/s) == null) {
            console.dir({ textGroupRaw, textGroupRawParsed });
            throw new Error(`unexpected replacement: ${JSON.stringify(textGroupRaw[0])}`);
          }
          // whitespace. usually this is indent of lines
          const whitespaceBetweenParts = textGroupRaw[0];
          textGroupRawParsed.textBlockTextPartList.push(whitespaceBetweenParts);
          textGroupRawParsed.textBlockTextPartIsTextList.push(false);
          // TODO later: add whitespace to translations
          /*
          // TODO rename "LineList" to "PartList"
          for (const translationLineList of Object.values(textGroupRawParsed.translations)) {
            translationLineList.push(whitespaceAfterLastTextPart);
          }
          */
        }
      }
      else {
        // textGroupRaw[1] == 0
        // add text part to text block
        //textGroupRawParsed.sourceTextBlockText += textGroupRaw[0];
        textGroupRawParsed.textBlockTextPartList.push(textGroupRaw[0]);
        textGroupRawParsed.textBlockTextPartIsTextList.push(true);
      }
    }
    // done: add values to textGroupRawParsed.textBlockTextPartList

    //console.log(`reading ${joinedTranslationsPath}`);
    const joinedTranslationsTextRaw = fs.readFileSync(joinedTranslationsPath, 'utf8');

    //console.log(`reading ${splittedTranslationsPath}`);
    const splittedTranslationsTextRaw = fs.readFileSync(splittedTranslationsPath, 'utf8');

    //let splittedTranslationsText = fs.readFileSync(translationsPathList, 'utf8');

    // cleanup translation text
    function cleanupTranslation(text) {
      // TODO keep the original translations somewhere
      // currently, they are stored in translations-google-store/
      return (
        text
        // remove unwanted characters
        .replace(new RegExp(`[${removeRegexCharClass}]`, 'g'), '')
        // fix double quotes
        // https://www.fileformat.info/info/unicode/char/0022/index.htm
        .replace(/[\u201c\u201d\u201e\u2033\u02dd\u030b\u030e\u05f4\u3003]/g, '"')
        // fix single quotes
        // https://www.fileformat.info/info/unicode/char/0027/index.htm
        .replace(/[\u2018\u2019\u02b9\u02bc\u02c8\u0301\u030d\u05f3\u2032]/g, "'")
        // move comma out of quotes
        // a: x said "foo," and "bar".
        // b: x said "foo", and "bar".
        .replace(/,"/g, '",')
        // TODO? replace "asdf..." with "asdf ..."
        // = replace /([a-z])\.\.\.\b/ with "$1 ..."
        // this is a matter of taste...
        // which is better ...?
        // space or no space?
        // i tend to prefer space
        .replace(/([a-z])\.\.\.(\b|$)/sg, "$1 ...")
      );
    }

    const joinedTranslationsText = cleanupTranslation(joinedTranslationsTextRaw);
    const splittedTranslationsText = cleanupTranslation(splittedTranslationsTextRaw);

    // combine content of "joined" and structure of "splitted" translations
    // this is simple with "git diff":
    /*
      git diff --word-diff=color --word-diff-regex=. --no-index \
        $(readlink -f $(ls -t -d translations-google-2023-* | head -n1)/de-en-000-j*) \
        $(readlink -f $(ls -t -d translations-google-2023-* | head -n1)/de-en-000-s*) |
        sed -E $'s/\e\[32m.*?\e\[m//g; s/\e\\[[0-9;:]*[a-zA-Z]//g' | tail -n +6 >todo-de-en-000.txt
    */

    // https://nodejs.org/api/child_process.html
    function execProcess(args, options) {
      if (!options) {
        options = {};
      }
      const execOptions = {
        encoding: "utf8",
        // TODO? dont buffer, write stdout to file
        maxBuffer: 100*1024*1024, // 100 MiB
        windowsHide: true,
        //timeout: 123,
        //cwd: "/",
        //input: "hello",
        ...options,
      };
      const proc = child_process.spawnSync(args[0], args.slice(1), execOptions);
      if (!options.allowNonZeroStatus) {
        if (proc.status != 0) {
          console.dir({ proc, args, argsJoined: args.join(" ") }); // debug
          throw new Error(`command ${args[0]} failed with status ${proc.status}`);
        }
      }
      return proc;
    }

    const systemUserId = execProcess(["id", "-u"]).stdout.trim();
    const tempdirPath = `/run/user/${systemUserId}`;

    const joinedTranslationsTextTempPath = `${tempdirPath}/translate-js-translation-joined.txt`;
    const splittedTranslationsTextTempPath = `${tempdirPath}/translate-js-translation-splitted.txt`;

    //console.log(`writing ${joinedTranslationsTextTempPath}`);
    fs.writeFileSync(joinedTranslationsTextTempPath, joinedTranslationsText);

    //console.log(`writing ${splittedTranslationsTextTempPath}`);
    fs.writeFileSync(splittedTranslationsTextTempPath, splittedTranslationsText);

    const gitDiffArgs = [
      "git", "diff",
      "--no-index", // compare files outside a git repo
      "--word-diff=color", // produce a fine-grained diff
      // TODO also run "git diff" without this option, to get more translation candidates
      "--word-diff-regex=.", // character diff: compare every character, also whitespace
    ];

    /*
    "character diff" and "word diff" produce different errors

    example:

    character diff splits "if"
    word diff joins "typelives"

    sourceTextBlockIdx: 107,
    textBlockTextPartList: [ 'Umgekehrt gilt:', 'Wenn ein Persönlichkeitstyp' ],
    splittedTranslationLineList: [ 'Conversely:', 'If a personality type' ],
    joinedTranslationLineList: [ 'Conversely, i', 'f a personality type lives' ]   // character diff
    joinedTranslationLineList: [ 'Conversely, if', 'a personality typelives' ]     // word diff
    */

    const gitDiffJoinedSplittedArgs = [
      ...gitDiffArgs,
      joinedTranslationsTextTempPath,
      splittedTranslationsTextTempPath,
    ];
    const gitDiffOptions = {
      allowNonZeroStatus: true,
    };
    let diffBodyStartPos;

    const diffJoinedSplittedTranslationsText = execProcess(gitDiffJoinedSplittedArgs, gitDiffOptions).stdout;
    diffBodyStartPos = 0;
    for (let i = 0; i < 5; i++) {
      diffBodyStartPos = diffJoinedSplittedTranslationsText.indexOf("\n", diffBodyStartPos + 1);
    }
    diffBodyStartPos++;
    // ansi codes escape byte: $'\e' in bash == '\x1b' in javascript
    // diff splitted joined: delete green text (color 32), keep red text (color 31)
    const combinedJoinedSplittedTranslationsText = diffJoinedSplittedTranslationsText.slice(diffBodyStartPos).replace(/\x1b\[32m.*?\x1b\[m/sg, "").replace(/\x1b\[[0-9;:]*[a-zA-Z]/sg, "")

    // not used. this diff has worse quality. i keep this for debugging
    const debugAlsoDoTheOtherDiff = false;

    if (debugAlsoDoTheOtherDiff) {
      const gitDiffSplittedJoinedArgs = [
        ...gitDiffArgs,
        splittedTranslationsTextTempPath,
        joinedTranslationsTextTempPath,
      ];
      const diffSplittedJoinedTranslationsText = execProcess(gitDiffSplittedJoinedArgs, gitDiffOptions).stdout;
      diffBodyStartPos = 0;
      for (let i = 0; i < 5; i++) {
        diffBodyStartPos = diffSplittedJoinedTranslationsText.indexOf("\n", diffBodyStartPos + 1);
      }
      diffBodyStartPos++;
      // ansi codes escape byte: $'\e' in bash == '\x1b' in javascript
      // diff splitted joined: delete red text (color 31), keep green text (color 32)
      const combinedSplittedJoinedTranslationsText = diffSplittedJoinedTranslationsText.slice(diffBodyStartPos).replace(/\x1b\[31m.*?\x1b\[m/sg, "").replace(/\x1b\[[0-9;:]*[a-zA-Z]/sg, "")

      const diffSplittedJoinedTranslationsTextTempPath = `${tempdirPath}/translate-js-translation-diff-splitted-joined.txt`;
      const combinedSplittedJoinedTranslationsTextTempPath = `${tempdirPath}/translate-js-translation-combined-splitted-joined.txt`;

      console.log(`writing ${diffSplittedJoinedTranslationsTextTempPath}`);
      fs.writeFileSync(diffSplittedJoinedTranslationsTextTempPath, diffSplittedJoinedTranslationsText);

      console.log(`writing ${combinedSplittedJoinedTranslationsTextTempPath}`);
      fs.writeFileSync(combinedSplittedJoinedTranslationsTextTempPath, combinedSplittedJoinedTranslationsText);
    }

    const debugDiff = false;

    if (debugDiff == false) {
      // remove temporary files
      fs.unlinkSync(splittedTranslationsTextTempPath);
      fs.unlinkSync(joinedTranslationsTextTempPath);
    }
    else {
      // keep temporary files
      console.log(`keeping ${splittedTranslationsTextTempPath}`);
      console.log(`keeping ${joinedTranslationsTextTempPath}`);

      // write more temporary files
      const diffJoinedSplittedTranslationsTextTempPath = `${tempdirPath}/translate-js-translation-diff-joined-splitted.txt`;
      const combinedJoinedSplittedTranslationsTextTempPath = `${tempdirPath}/translate-js-translation-combined-joined-splitted.txt`;

      console.log(`writing ${diffJoinedSplittedTranslationsTextTempPath}`);
      fs.writeFileSync(diffJoinedSplittedTranslationsTextTempPath, diffJoinedSplittedTranslationsText);

      console.log(`writing ${combinedJoinedSplittedTranslationsTextTempPath}`);
      fs.writeFileSync(combinedJoinedSplittedTranslationsTextTempPath, combinedJoinedSplittedTranslationsText);
    }

    const splittedTranslationsList = splittedTranslationsText.trim().split("\n");

    // TODO rename to joinedTranslationsList
    const combinedJoinedSplittedTranslationsList = combinedJoinedSplittedTranslationsText.trim().split("\n");
    //const combinedSplittedJoinedTranslationsList = combinedSplittedJoinedTranslationsText.trim().split("\n");

    let lastSplittedTranslationIdx = -1;

    // TODO are these "lines" or "blocks"?
    let textGroupRawParsedIdx;

    // note: textGroupRawParsedIdxLast + 1 != textGroupRawParsedList.length
    // ... because new values were added in the "add values to textGroupRawParsedList" loop
    // we could also save textGroupRawParsedIdxLast before the "add values to textGroupRawParsedList" loop

    let textGroupRawParsedIsFirst = true;

    let textBlockTextPartIdx;

    if (debugTextGroupRawParser) {
      console.log(`line 3250: textGroupRawParsedIdxLast ${textGroupRawParsedIdxLast}`)
    }

    // loop text parts: add aligned translations to textGroupRawParsedList
    for (textGroupRawParsedIdx = textGroupRawParsedIdxLast; textGroupRawParsedIdx < textGroupRawParsedList.length; textGroupRawParsedIdx++) {

      if (debugTextGroupRawParser) {
        console.log(`line 3250: textGroupRawParsedIdx ${textGroupRawParsedIdx}`)
      }

      // TODO opposite?
      if (textGroupRawParsedIsFirst) {
        // continue
        if (debugAlignment) {
          console.log(`line 3260: textBlockTextPartIdxNext ${textBlockTextPartIdxNext} -> ${textBlockTextPartIdxNextLast}`);
        }
        textBlockTextPartIdxNext = textBlockTextPartIdxNextLast;
        textGroupRawParsedIsFirst = false;
      }
      else {
        // reset
        if (debugAlignment) {
          console.log(`line 3260: textBlockTextPartIdxNext ${textBlockTextPartIdxNext} -> 0`);
        }
        textBlockTextPartIdxNext = 0;
      }

      debugAlignment &&
      console.log(`translatedFileId ${String(translatedFileId).padStart(5)}   textGroupRawParsedIdx ${String(textGroupRawParsedIdx).padStart(5)}`);

      // textGroupsRawIdx: index of sourceTextLine in the textGroupsRaw array
      const textGroupRawParsed = textGroupRawParsedList[textGroupRawParsedIdx];

      // TODO is this "text line" or "text block"?
      // none of both. this is a "text part" = "text line" or part of a "text line"
      // TODO rename sourceTextLine to sourceTextPart
      // the name wont get better than "part". its just one or more words
      // but it never contains newlines
      const textBlockTextPartList = textGroupRawParsed.textBlockTextPartList;
      const textBlockTextPartIsTextList = textGroupRawParsed.textBlockTextPartIsTextList;

      let stopLoopSourceTextPartsLoop = false;

      // parent loop
      if (debugAlignment) {
        console.log(`line 3030: translatedFileId ${translatedFileId}`)
      }

      if (debugAlignment) {
        console.log(`line 3030: looping textBlockTextPartIdx from ${textBlockTextPartIdxNext} to ${textBlockTextPartList.length - 1}`)
      }

      debugAlignment &&
      console.log(`loop from next ...`);

      // loop text parts of this text block from next
      for (textBlockTextPartIdx = textBlockTextPartIdxNext; textBlockTextPartIdx < textBlockTextPartList.length; textBlockTextPartIdx++) {

        //console.log(`    loop text parts of this text block: textBlockTextPartIdx ${textBlockTextPartIdx}`);
        debugAlignment &&
        console.log(`loop from next: translatedFileId ${String(translatedFileId).padStart(5)}   textGroupRawParsedIdx ${String(textGroupRawParsedIdx).padStart(5)}   textBlockTextPartIdx ${String(textBlockTextPartIdx).padStart(5)}`);

        const textBlockTextPart = textBlockTextPartList[textBlockTextPartIdx];
        const textBlockTextPartIsText = textBlockTextPartIsTextList[textBlockTextPartIdx];

        if (textBlockTextPartIsText == false) {
          // this part is whitespace
          const whitespacePartContent = textBlockTextPart;
          /*
          textGroupRawParsed.translations.splittedTranslationLineList[textBlockTextPartIdx] = translatedTextLineSplitted;
          textGroupRawParsed.translations.joinedTranslationLineList[textBlockTextPartIdx] = translatedTextLineCombinedJoinedSplitted;
          */
          // read from text group raw parsed translations
          for (const translationLineList of Object.values(textGroupRawParsed.translations)) {
            //translationLineList.push(whitespacePartContent);
            translationLineList[textBlockTextPartIdx] = whitespacePartContent;
          }
          continue;
        }

        // TODO rename sourceTextLine to textBlockTextPart
        // source_text_line = text_block
        const sourceTextLine = textBlockTextPart;

        debugAlignment &&
        console.log(`a=${translatedFileId} b=${textGroupRawParsedIdx} c=${textBlockTextPartIdx} textBlockTextPart ${JSON.stringify(textBlockTextPart)}`);

        /*
        if (sourceTextLine.indexOf("\n") > -1) {
          console.dir({ textGroupRawParsedIdx, textGroupRawParsed, sourceTextLine });
          throw new Error(`sourceTextLine contains newline`);
        }
        */

        //console.dir({ lastSplittedTranslationIdx, sourceTextLine });

        //const sourceTextLineTrimmed = sourceTextLine.trim();
        let translatedTextLineSplitted = null;
        let translatedTextLineCombinedJoinedSplitted = null;

        /*
        if (sourceTextLineTrimmed.indexOf("\n") > -1) {
          //console.dir({ sourceTextLineIdx, sourceTextLine, textGroupsRawIdx, sourceTextLineTrimmed });
          console.dir({ textGroupRawParsedIdx, textGroupRawParsed, sourceTextLine, sourceTextLineTrimmed });
          throw new Error(`sourceTextLineTrimmed contains newline`);
        }
        */

        // find translated text in splittedTranslationsList

        // find "splitted" translation of this source text part
        // loop lines of the "splitted" translations
        let splittedTranslationIdx;
        for (
          splittedTranslationIdx = lastSplittedTranslationIdx + 1;
          splittedTranslationIdx < splittedTranslationsList.length;
          splittedTranslationIdx++
        ) {
          // this is always just one line (or less)
          const splittedTranslationLine = splittedTranslationsList[splittedTranslationIdx];
          if (debugAlignment) {
            console.log(`a=${translatedFileId} b=${textGroupRawParsedIdx} c=${textBlockTextPartIdx} d=${splittedTranslationIdx} sourceTextLine + splittedTranslationLine = ${JSON.stringify(sourceTextLine)} + ${JSON.stringify(splittedTranslationLine)}`)
          }
          if (
            // source is empty line
            sourceTextLine.match(/^\s*$/s) != null &&
            // translation is not empty line
            splittedTranslationLine.match(/^\s*$/s) == null
          ) {
            // copy whitespace from source
            translatedTextLineSplitted = sourceTextLine;
            translatedTextLineCombinedJoinedSplitted = sourceTextLine.trim();
            // dont use splittedTranslationLine
            // dont update lastSplittedTranslationIdx
            break;
          }
          if (
            // source is "."
            //sourceTextLine.match(/^\s*\.\s*$/s) != null &&
            sourceTextLine == "." &&
            // translation is not "."
            // translators can remove lines with only "."
            splittedTranslationLine.match(/^\s*\.\s*$/s) == null
          ) {
            // copy "." from source
            translatedTextLineSplitted = sourceTextLine;
            translatedTextLineCombinedJoinedSplitted = sourceTextLine.trim();
            // dont use splittedTranslationLine
            // dont update lastSplittedTranslationIdx
            break;
          }

          if (
            // source is not "."
            sourceTextLine != "." &&
            // translation is "."
            splittedTranslationLine.match(/^\s*\.\s*$/s) != null
          ) {
            // ignore this translation
            continue;
          }
          
          // use this translated line
          // TODO restore whitespace from sourceTextLine?
          translatedTextLineSplitted = splittedTranslationLine;

          // TODO is it that simple?
          // this assumes that "splitted" and "combined" lines are aligned
          if (combinedJoinedSplittedTranslationsList[splittedTranslationIdx] == undefined) {
            console.error(`warning: missing combined translation for ${sourceLang}-${targetLang}-${String(translatedFileId).padStart(3, "0")}:${splittedTranslationIdx}`);
            // warning: missing combined translation for de-en-006:173
          }
          translatedTextLineCombinedJoinedSplitted = (combinedJoinedSplittedTranslationsList[splittedTranslationIdx] || "").trim();

          lastSplittedTranslationIdx = splittedTranslationIdx;
          break;
          //console.dir({ splittedTranslation });
          //throw new Error("todo");
        }
        // done: loop lines of the "splitted" translations

        debugAlignment &&
        console.log(`translatedFileId ${String(translatedFileId).padStart(5)}   textGroupRawParsedIdx ${String(textGroupRawParsedIdx).padStart(5)}   textBlockTextPartIdx ${String(textBlockTextPartIdx).padStart(5)}   splittedTranslationIdx ${String(splittedTranslationIdx).padStart(5)}`);

        if (translatedTextLineSplitted == null) {

          console.dir({
            sourceTextLine,
            translatedTextLineSplitted,
            translatedTextLineCombinedJoinedSplitted,
          });

          throw new Error(`not found "splitted" translation of sourceTextLine: ${JSON.stringify(sourceTextLine)}`);

        }

        if (translatedTextLineCombinedJoinedSplitted == null) {
          // this should never happen
          // the loop should have stopped because translatedTextLineSplitted was not found
          console.dir({ translatedTextLineSplitted });
          throw new Error(`not found "combined" translation of sourceTextLine: ${sourceTextLine}`);
        }

        // write to text group raw parsed translations
        textGroupRawParsed.translations.splittedTranslationLineList[textBlockTextPartIdx] = translatedTextLineSplitted;
        textGroupRawParsed.translations.joinedTranslationLineList[textBlockTextPartIdx] = translatedTextLineCombinedJoinedSplitted;

      }
      // done: loop text parts of this text block from next

      if (stopLoopSourceTextPartsLoop) {
        break;
      }

    }
    // done: loop text parts: add aligned translations to textGroupRawParsedList

    debugAlignment &&
    console.log(`line 3500: textGroupRawParsedIdx ${textGroupRawParsedIdx}   textGroupRawParsedIdxLast ${textGroupRawParsedIdxLast}`);

    // undo "textGroupRawParsedIdx++" in the previous for loop
    textGroupRawParsedIdxLast = textGroupRawParsedIdx - 1;

    debugAlignment &&
    console.log(`line 3505: textGroupRawParsedIdx ${textGroupRawParsedIdx}   textGroupRawParsedIdxLast ${textGroupRawParsedIdxLast}`);

    debugAlignment &&
    console.log(`line 3510: textBlockTextPartIdxNextLast ${textBlockTextPartIdxNextLast} -> ${textBlockTextPartIdx}`);

    // note: textBlockTextPartIdx was incremented after the last iteration
    // of "loop text parts of this text block from next"
    // textBlockTextPartIdx++
    textBlockTextPartIdxNextLast = textBlockTextPartIdx;

  }
  // done: loop input files: add source and translated text parts to textGroupRawParsed

  console.log(`populating textGroupRawParsedList done`);



  console.log(`autofixing and autosolving translations ...`);

  // autofix and autosolve translations
  // no. later: write translatedText and translatedHtml

  let textGroupRawParsedLast; // debug

  // TODO merge with previous loop
  // loop source text lines: autofix and autosolve translations in textGroupRawParsed
  //for (let sourceTextLineIdx = 0; sourceTextLineIdx < textGroupRawTextList.length; sourceTextLineIdx++) {
  //for (let textBlockIdx = textBlockIdxLastOfLastInputFile + 1; textBlockIdx < TODO.length; textBlockIdx++) {
  for (let textBlockIdx = 0; textBlockIdx < textGroupRawParsedList.length; textBlockIdx++) {

    debugAlignment &&
    console.log(`textBlockIdx ${String(textBlockIdx).padStart(5)}`);

    const textGroupRawParsed = textGroupRawParsedList[textBlockIdx];

    // if process.stdout is not a terminal, use this default width
    const defaultTerminalWidth = 156;

    //const sourceTextLineTrimmed = sourceTextLineList[sourceTextLineIdx].trim();
    /*
    const sourceTextLine = textGroupRawTextList[sourceTextLineIdx][0]; // TODO remove?
    const sourceTextLineTrimmed = textGroupRawTextList[sourceTextLineIdx][0].trim();
    */

    const textBlockTextPartList = textGroupRawParsed.textBlockTextPartList;

    let textBlockTextPartIdx;

    debugAlignment &&
    console.log(`loop from first ...`);

    // loop text parts of this text block from first
    for (textBlockTextPartIdx = 0; textBlockTextPartIdx < textBlockTextPartList.length; textBlockTextPartIdx++) {

      debugAlignment &&
      console.log(`loop from first: textBlockIdx ${String(textBlockIdx).padStart(5)}   textBlockTextPartIdx ${String(textBlockTextPartIdx).padStart(5)}   (translatedFileId ${String(textGroupRawParsed.translatedFileId).padStart(5)})`);

      const textBlockTextPart = textBlockTextPartList[textBlockTextPartIdx];
      // TODO rename sourceTextLine to textBlockTextPart
      const sourceTextLine = textBlockTextPart;

      const sourceTextLineTrimmed = sourceTextLine.trim();

      debugAlignment &&
      console.log(`3550 sourceTextLineTrimmed ${JSON.stringify(sourceTextLineTrimmed)}`)

      if (
        // this part is whitespace only
        textGroupRawParsed.textBlockTextPartIsTextList[textBlockTextPartIdx] == false ||
        // this part is punctuation only
        sourceTextLineTrimmed == "." ||
        sourceTextLineTrimmed == "," ||
        sourceTextLineTrimmed == ":" ||
        false
        // TODO exclude more?
      ) {
        continue;
      }

      //console.log(`alignments for sourceTextLineTrimmed: ${sourceTextLineTrimmed}`);
      /*
      const translatedTextLineSplitted = splittedTranslationLineList[sourceTextLineIdx];
      const translatedTextLineCombinedJoinedSplitted = joinedTranslationLineList[sourceTextLineIdx];
      */
      // read from text group raw parsed translations
      const translatedTextLineSplitted = textGroupRawParsed.translations.splittedTranslationLineList[textBlockTextPartIdx];
      const translatedTextLineCombinedJoinedSplitted = textGroupRawParsed.translations.joinedTranslationLineList[textBlockTextPartIdx];

      //console.log(`textGroupRawParsed.translatedFileId ${textGroupRawParsed.translatedFileId}`);

      // debug
      // FIXME translatedTextLineCombinedJoinedSplitted == undefined
      if (debugAlignment && textGroupRawParsed.translatedFileId >= 82) {
        console.dir({ textBlockIdx, textGroupRawParsed });
      }

      if (translatedTextLineCombinedJoinedSplitted == undefined) {
        console.dir({ textBlockIdx, textGroupRawParsed, textGroupRawParsedLast, textBlockTextPartIdx, translatedTextLineCombinedJoinedSplitted, translatedTextLineSplitted }, { depth: null});
        // wrong textBlockIdx?
        throw new Error("FIXME translatedTextLineCombinedJoinedSplitted == undefined");
      }

      if (translatedTextLineSplitted == undefined) {
        console.dir({ textBlockIdx, textGroupRawParsed, textGroupRawParsedLast, textBlockTextPartIdx, translatedTextLineCombinedJoinedSplitted, translatedTextLineSplitted }, { depth: null});
        throw new Error("FIXME translatedTextLineSplitted == undefined");
      }

      // TODO move out

      function autofixTranslations(sourceText, translatedTextList, targetLang) {
        if (targetLang == "en") {
          translatedTextList = translatedTextList.map(translatedText => {
            // \b = word boundary
            // https://developer.mozilla.org/en-US/docs/Web/JavaScript/Reference/Regular_expressions/Word_boundary_assertion
            return (
              translatedText
              // i really hate these abbreviations...
              // so i dont want them in my text
              // or rather: i "do not" want them in my text...
              // de-en-000:125:
              //   s: (Die vier Typen erkläre ich später.)
              //   t: (I'll explain the four types later.)
              .replace(/\b(i|you|he|she|it|we|they)'ll\b/gi, "$1 will")
              // de-en-021:10:
              //   s: Wohnst du aber nicht dort, so erfährst du von ihnen erst,
              //   t: But if you don't live there, you will only find out about them when,
              //   t: But if you don't live there, you will only find out from them when,
              .replace(/\b(w)on't\b/gi, "$1ill not")
              .replace(/\b(c)an't\b/gi, "$1an not")
              // de-en-052:62:
              //   s: dann sind für ihn Freunde nicht so wichtig.
              //   t: then friends aren't that important to them.
              //   t: then friends aren't that important to him.
              .replace(/\b(do|does|did|is|was|were|should|could|have|would|are)n't\b/gi, "$1 not")
              // de-en-021:11:
              //   s: wenn sie sich schon weit ausgebreitet haben
              //   t: they've already spread widely
              //   t: when they have already spread widely
              .replace(/\b(i|you|they|we)'ve\b/gi, "$1 have")
              .replace(/\b(i|you|he|she|it|we|they)'d\b/gi, "$1 would")
              // de-en-021:12:
              //   s: und es kein Mittel mehr dagegen gibt.
              //   t: and there's no longer any way to stop them.
              //   t: and there is no longer any remedy against it.
              // de-en-050:5:
              //   s: und sage gleich was Sache ist.
              //   t: and say what's going on straight away.
              //   t: and say straight away what's going on.
              .replace(/\b(who|that|there|what|it)'s\b/gi, "$1 is")

              .replace(/\b(i)'m\b/gi, "$1 am")
              .replace(/\b(you|we|they)'re\b/gi, "$1 are")
              .replace(/\b(he|she|it)'s\b/gi, "$1 is")

              .replace(/\b(let)'s\b/gi, "$1 us")

              // TODO what is "e's"?
              // de-en-047:43:
              //   s: über die Dummheit der Menschen...
              //   t: e's stupidity...
              //   t: about the stupidity of people...

            );
          });
        }
        return translatedTextList;
      }

      // TODO move out

      // autosolve translations
      function autosolveTranslations(sourceText, translatedTextList) {

        // TODO maybe use other autosolve for other targetLang

        if (translatedTextList.length <= 1) {
          // 0 or 1 translation. no translations to compare
          if (debugAlignment) {
            console.log(`3670 autosolveTranslations 1`)
          }
          return translatedTextList;
        }

        // de-en-000:104:
        //   s: Personality Type.
        //   t: Personality Type.
        //   t: Personality type.
        // source and translations are equal
        for (const translatedText of translatedTextList) {
          if (translatedText == sourceText) {
            if (debugAlignment) {
              console.log(`3670 autosolveTranslations 2`)
            }
            return [translatedText];
          }
        }

        // all translations are equal
        const firstTranslatedText = translatedTextList[0];
        let allTranslationsAreEqual = true;
        for (let translationId = 1; translationId < translatedTextList.length; translationId++) {
          const translatedText = translatedTextList[translationId];
          if (translatedText != firstTranslatedText) {
            allTranslationsAreEqual = false;
            break;
          }
        }
        if (allTranslationsAreEqual) {
          if (debugAlignment) {
            console.log(`3670 autosolveTranslations 3`)
          }
          return [firstTranslatedText];
        }

        if (debugAlignment) {
          console.log(`3670 autosolveTranslations 4`)
        }

        // check for trivial differences

        // TODO also check combinations of these cases
        //   example: wrong end punctuation + wrong casing of first character

        const endPunctuationRegex = /[.,?!" ]+$/s;
        const onlyPunctuationRegex = /^[.,?!" ]+$/s;

        // get line end punctuation
        function getLineEndPunctuation(line) {
          return (line.match(endPunctuationRegex) || [])[0];
        }

        const sourceTextEndPunctuation = getLineEndPunctuation(sourceText);

        if (debugAlignment) {
          console.log(`3710 autosolveTranslations 4 sourceTextEndPunctuation ${JSON.stringify(sourceTextEndPunctuation || null)}`);
        }

        if (sourceTextEndPunctuation != undefined) {
          // source line ends with punctuation
          // prefer translations that also end with the same punctuation
          // but otherwise have the same prefix
          // example:
          // de-en-000:70:
          //   s: Nur wenige Weltbilder geben eine Antwort,
          //   t: Only a few worldviews provide an answer
          //   t: Only a few worldviews provide an answer,
          translatedTextList.map(translatedText => {
            if (translatedText.endsWith(sourceTextEndPunctuation) == false) {
              if (debugAlignment) {
                console.log(`3670 autosolveTranslations 4 1`)
              }
              return;
            }
            // translatedText has same end punctuation as sourceText
            // remove other translated texts that only differ in end punctuation

            const translatedTextBeforeEndPunctuation = translatedText.slice(0, -1 * sourceTextEndPunctuation.length);

            if (debugAlignment) {
              console.log(`3670 autosolveTranslations 4 1 translatedTextBeforeEndPunctuation ${JSON.stringify(translatedTextBeforeEndPunctuation)}`)
            }

            translatedTextList = translatedTextList.filter(translatedText2 => {
              if (
                translatedText2.startsWith(translatedTextBeforeEndPunctuation) == false ||
                translatedText2 == translatedText
              ) {
                if (debugAlignment) {
                  console.log(`3670 autosolveTranslations 4 2`)
                }
                return true; // keep translation
              }
              // translatedText2 has same prefix as translatedText, but a different suffix
              const suffix = translatedText2.slice(translatedTextBeforeEndPunctuation.length);
              if (
                suffix == "" ||
                suffix.match(onlyPunctuationRegex) != null
              ) {
                // suffix has no words
                if (debugAlignment) {
                  console.log(`3670 autosolveTranslations 4 3`)
                }
                return false; // remove translation
              }
              // suffix has words
              if (debugAlignment) {
                console.log(`3670 autosolveTranslations 4 4`)
              }
              return true; // keep translation
            });
          });
          if (debugAlignment) {
            console.log(`3670 autosolveTranslations 5`)
          }
          // add missing end punctuation to translated texts
          // de-en-000:89:
          //   s: Wie müssen wir verschiedene Menschen verbinden,
          //   t: How do we need to connect different people
          //   t: How do we have to connect different people,
          translatedTextList = translatedTextList.map(translatedText => {
            if (translatedText.endsWith(sourceTextEndPunctuation)) {
              return translatedText; // no change
            }
            const suffix = getLineEndPunctuation(translatedText);
            /*
            if (sourceText == "Wie müssen wir verschiedene Menschen verbinden,") {
              console.dir({
                sourceText,
                translatedText,
                suffix,
              });
            }
            */
            if (suffix == undefined) {
              // translated text does NOT end with punctuation
              // add end punctuation
              return translatedText + sourceTextEndPunctuation;
            }
            return translatedText; // no change
          });
        }
        else {
          if (debugAlignment) {
            console.log(`3670 autosolveTranslations 6`)
          }
          // source line does not end with punctuation
          // sourceTextEndPunctuation == undefined
          // source line does NOT end with punctuation
          // prefer translations that also do NOT end with punctuation
          // but otherwise have the same prefix
          // example:
          // de-en-000:27:
          //   s: Wer sind meine Freunde
          //   t: Who are my friends
          //   t: Who are my friends?
          translatedTextList.map(translatedText => {
            const translatedTextEndPunctuation = getLineEndPunctuation(translatedText);
            if (translatedTextEndPunctuation != undefined) {
              if (debugAlignment) {
                console.log(`3670 autosolveTranslations 6 1 translatedTextEndPunctuation ${JSON.stringify(translatedTextEndPunctuation)}`)
              }
              return;
            }
            if (debugAlignment) {
              console.log(`3670 autosolveTranslations 6 1 translatedText ${JSON.stringify(translatedText)}`)
            }
            // translatedTextEndPunctuation == undefined
            // translatedText also has NO end punctuation
            // remove other translated texts that only differ in end punctuation
            translatedTextList = translatedTextList.filter(translatedText2 => {
              if (debugAlignment) {
                console.log(`3670 autosolveTranslations 6 1.5 translatedText2 ${JSON.stringify(translatedText2)}`);
              }
              if (translatedText2 == translatedText) {
                if (debugAlignment) {
                  console.log(`3670 autosolveTranslations 6 2`)
                }
                return true; // keep translation
              }
              if (translatedText2.startsWith(translatedText)) {
                // translatedText2 has same prefix as translatedText, but a different suffix
                if (debugAlignment) {
                  console.log(`3670 autosolveTranslations 6 3`)
                }
                return false; // remove translation
              }
              if (debugAlignment) {
                console.log(`3670 autosolveTranslations 6 4`)
              }
              return true; // keep translation
            });
          });
        }

        // no. dont autosolve this
        // first character has different casing: lowercase versus uppercase
        // example:
        // de-en-000:43:
        //   s: Menschen mit Zukunft.
        //   t: people with a future.
        //   t: People with a future.
        // bad example:
        // de-en-000:60:
        //   s: Menschen.
        //   t: people.
        //   t: People.

        // return the filtered translation list
        return translatedTextList;
      }

      let translatedTextLineList = [
        translatedTextLineCombinedJoinedSplitted,
        translatedTextLineSplitted,
        // TODO add more translations: argos translate, deepl translator
      ];

      // first autofix, then autosolve
      // because autofix can produce more identical translations
      // which are then reduced by autosolve

      if (debugAlignment) {
        console.log("3840 sourceTextLineTrimmed", JSON.stringify(sourceTextLineTrimmed));
        console.log("3840 translatedTextLineList", JSON.stringify(translatedTextLineList));
      }

      translatedTextLineList = autofixTranslations(sourceTextLineTrimmed, translatedTextLineList, targetLang);

      if (debugAlignment) {
        console.log("3845 translatedTextLineList", JSON.stringify(translatedTextLineList));
      }

      translatedTextLineList = autosolveTranslations(sourceTextLineTrimmed, translatedTextLineList);

      if (debugAlignment) {
        console.log("3850 translatedTextLineList", JSON.stringify(translatedTextLineList));
      }

      // write to text group raw parsed translations
      // write back to textGroupRawParsed.translations
      // first translation in translatedTextLineList is the "joined" translation
      textGroupRawParsed.translations.joinedTranslationLineList[textBlockTextPartIdx] = (
        translatedTextLineList[0]
      );
      textGroupRawParsed.translations.splittedTranslationLineList[textBlockTextPartIdx] = (
        // second translation in translatedTextLineList is the "splitted" translation
        // if it was removed by autosolve, the just copy the "joined" translation
        translatedTextLineList[1] ||
        translatedTextLineList[0]
      );

      textGroupRawParsedLast = textGroupRawParsed;

    }
    // done: loop text parts of this text block from first

  }
  // done: loop source text lines: autofix and autosolve translations in textGroupRawParsed

  console.log(`autofixing and autosolving translations done`);

  // TODO use translatedTextLineList



  // debug

  const textGroupRawParsedListPath = "debug-textGroupRawParsedList.json";
  console.log(`writing ${textGroupRawParsedListPath}`);
  fs.writeFileSync(textGroupRawParsedListPath, JSON.stringify(textGroupRawParsedList, null, 2));



  // TODO? transform textGroupRawParsedList to object
  // using sourceTextBlockHash as key



  // now all translations are aligned, autofixed, autosolved
  // so we can loop source texts in order
  // and reconstruct the html

  // TODO main loop: textToTranslateList + htmlBetweenReplacementsList
  // TODO write html. loop source text list, get translations from translatedTextLineListByInputFileList

  let translatedHtml = "";
  let translatedSplittedHtml = "";

  // debug: compare translations in plain text format
  // TODO make something similar in html
  // where we see vertical stacks of source text and translation candidates
  //let translatedText = "";

  for (let textToTranslateIdx = 0; textToTranslateIdx < textToTranslateList.length; textToTranslateIdx++) {

    //console.log(`textToTranslateIdx ${String(textToTranslateIdx).padStart(5)}`);

    const htmlBeforeText = htmlBetweenReplacementsList[textToTranslateIdx];
    translatedHtml += htmlBeforeText;
    translatedSplittedHtml += htmlBeforeText;
    const textToTranslateEntry = textToTranslateList[textToTranslateIdx];
    const [_idx, sourceHash, sourceLang, sourceText, todoRemoveEndOfSentence, todoAddToTranslationsDatabase] = textToTranslateEntry;
    // TODO how to get from textToTranslateEntry to translatedTextLineListByInputFileList
    //   ... or from textToTranslateEntry to translatedTextPartList
    // sourceLang is obvious
    // but how to get the position
    // also, if its not found in translatedTextLineListByInputFileList
    // then search in translationsDatabase
    // or first search in translationsDatabase...



    let translatedTextBlockText = undefined;
    let translatedSplittedTextBlockText = undefined;

    if (sourceHash == "") {
      translatedTextBlockText = "";
    }

    if (translatedTextBlockText == undefined) {
      const translationKey = sourceLang + ":" + targetLang + ":" + sourceHash;
      translatedTextBlockText = (translationsDatabase[translationKey] || [])[1];
    }

    //console.dir({ translatedText }); throw new Error("todo");
    // Pallas. Who are my friends? Group structure by personality type
    // FIXME trim whitespace
    // caused by junk data in translations-google-database-de-en.html
    // TODO rebuild the database from translated *.txt files
    // a: <title> Pallas. Who are my friends? Group structure by personality type</title>
    // b: <title>Pallas. Who are my friends? Group structure by personality type</title>

    if (translatedTextBlockText == undefined) {
      const textGroupRawParsed = textGroupRawParsedList.find(
        textGroupRawParsed => textGroupRawParsed.sourceTextBlockHash == sourceHash
      );
      if (textGroupRawParsed == undefined) {
        console.dir({
          textToTranslateIdx,
          sourceHash, sourceLang, sourceText, todoRemoveEndOfSentence, todoAddToTranslationsDatabase,
        });
        throw new Error("TODO find translation in translatedTextLineListByInputFileList")
      }
      // TODO also add the "splitted" translation (and other translations)
      // join text parts to text block
      /*
      const joinedTranslationBlockText = textGroupRawParsed.translations.joinedTranslationLineList.join("");
      const splittedTranslationBlockText = textGroupRawParsed.translations.splittedTranslationLineList.join("");
      if (joinedTranslationBlockText == splittedTranslationBlockText) {
        translatedTextBlockText = joinedTranslationBlockText;
      }
      else {
        translatedTextBlockText = (
          joinedTranslationBlockText +
          "<!-- splittedTranslation:\n" +
          splittedTranslationBlockText +
          "\n-->"
        );
      }
      */
      // no. the "joined" translation is better in most cases
      /*
      translatedTextBlockText = "";
      for (let partIdx = 0; partIdx < textGroupRawParsed.translations.joinedTranslationLineList.length; partIdx++) {
        const joinedPart = textGroupRawParsed.translations.joinedTranslationLineList[partIdx];
        const splittedPart = textGroupRawParsed.translations.splittedTranslationLineList[partIdx];
        if (joinedPart == splittedPart) {
          translatedTextBlockText += joinedPart;
        }
        else {
          const whitespaceBeforeSplittedPart = (
            textGroupRawParsed.textBlockTextPartIsTextList[partIdx - 1]
            // previous part is text
            ? ""
            // previous part is whitespace
            : textGroupRawParsed.translations.splittedTranslationLineList[partIdx - 1]
          );
          translatedTextBlockText += (
            joinedPart +
            "\n<!-- splittedTranslation:" +
            // note: whitespace can be empty string
            whitespaceBeforeSplittedPart +
            splittedPart +
            "\n-->"
          );
        }
      }
      */
      //console.dir({ translatedText }); throw new Error("todo");

      // read from text group raw parsed translations
      const joinedTranslationBlockText = textGroupRawParsed.translations.joinedTranslationLineList.join("");
      const splittedTranslationBlockText = textGroupRawParsed.translations.splittedTranslationLineList.join("");

      translatedTextBlockText = joinedTranslationBlockText;

      if (joinedTranslationBlockText != splittedTranslationBlockText) {
        // "joined" and "splitted" translations are different
        translatedSplittedTextBlockText = splittedTranslationBlockText;
      }
    }

    if (translatedTextBlockText == undefined) {
      console.dir({
        textToTranslateIdx,
        sourceHash, sourceLang, sourceText, todoRemoveEndOfSentence, todoAddToTranslationsDatabase,
      });
      throw new Error("FIXME missing translation for this text block");
    }

    translatedHtml += translatedTextBlockText;

    if (translatedSplittedTextBlockText == undefined) {
      // "joined" and "splitted" translations are equal
      translatedSplittedHtml += translatedTextBlockText;
    }
    else {
      // "joined" and "splitted" translations are different
      translatedSplittedHtml += translatedSplittedTextBlockText;
    }

  }

  // add last html chunk
  translatedHtml += htmlBetweenReplacementsList.slice(-1)[0];
  translatedSplittedHtml += htmlBetweenReplacementsList.slice(-1)[0];

  console.log(`writing ${translatedHtmlPath}`);
  fs.writeFileSync(translatedHtmlPath, translatedHtml, 'utf8');

  console.log(`writing ${translatedSplittedHtmlPath}`);
  fs.writeFileSync(translatedSplittedHtmlPath, translatedSplittedHtml, 'utf8');

  // TODO stringifyTranslationsDatabase

}



function stringifyTranslationsDatabase(translationsDatabase, languagePair) {
  // to produce editable html, see translations-database.js
  let result = `<h1>translations database ${languagePair}</h1>\n`;
  // note: sorting translations by hash will produce a random order
  // the human-readable order of translations is restored in importLang
  const translationKeyPrefix = languagePair + ":";
  for (const translationKey of Object.keys(translationsDatabase).sort()) {
    if (!translationKey.startsWith(translationKeyPrefix)) {
      continue;
    }
    const [sourceText, translatedText] = translationsDatabase[translationKey];
    const [_sourceLang, _targetLang, sourceHash] = translationKey.split(":");
    const sourceHashActual = sha1sum(sourceText);
    if (sourceHash != sourceHashActual) {
      console.error(`warning: stringifyTranslationsDatabase: sourceHash != sourceHashActual: ${sourceHash} != ${sourceHashActual}: sourceText = ${sourceText.slice(0, 100)} ...`);
    }
    result += `\n`
    result += `<h2 id="${translationKey}">${translationKey}</h2>\n`
    result += `<table style="width:100%"><tr>\n`
    result += `<td style="width:50%"><pre style="white-space:pre-wrap">\n${sourceText}\n</pre></td>\n`
    result += `<td style="width:50%"><pre style="white-space:pre-wrap">\n${translatedText}\n</pre></td>\n`
    result += `</tr></table>\n`
  }
  return result;
}



function parseTranslationsDatabase(translationsDatabase, translationsDatabaseText) {
  translationsDatabaseText = translationsDatabaseText.replace(
    /\n<h2 id="[^"]+">([^<]+)<\/h2>\n<table style="width:100%"><tr>\n<td style="width:50%"><pre style="white-space:pre-wrap">\n(.*?)\n<\/pre><\/td>\n<td style="width:50%"><pre style="white-space:pre-wrap">\n(.*?)\n<\/pre><\/td>\n<\/tr><\/table>\n/sg,
    (_matchText, translationKey, sourceText, translatedText) => {
      // debug
      //console.dir({_matchText, translationKey, sourceText, translatedText}); process.exit(1);
      const [sourceLang, targetLang, sourceHash] = translationKey.split(":");
      const sourceHashActual = sha1sum(sourceText);
      if (sourceHash != sourceHashActual) {
        console.error(`error: parseTranslationsDatabase: sourceHash != sourceHashActual: ${sourceHash} != ${sourceHashActual}: sourceText = ${sourceText.slice(0, 100)} ...`);
        throw new Error("fixme");
      }
      translationsDatabase[translationKey] = [sourceText, translatedText];
      return ""; // remove parsed text
    }
  );
  if (translationsDatabaseText.match(/^<h1>translations database [^< ]+<\/h1>\n$/s) == null) {
    console.error(`warning: parseTranslationsDatabase did not parse all input. rest:`, translationsDatabaseText);
  }
}



main();
