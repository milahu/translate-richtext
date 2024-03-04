# translate richtext

translate rich-text documents between human languages, online or offline

solve two conflicting goals:

1. preserve the original structure of the document, including whitespace, newlines, indents
2. preserve sentences across structure boundaries like `<p><b>hello</b> world.</p>`



## use cases

- translate text documents: html, epub, odt, docx, pdf, rtf, latex
- translate video subtitles: srt, vtt



## challenges



### preserve sentences

sentences may be broken by

- newlines in the source text
- markup tags

this is a problem, because when we feed sentence-parts to translators,
then the translators will return worse quality
than in the case, where we feed full sentences to translators



### align similar texts

our solution is using two translations:

1. a "splitted" translation
2. a "joined" translation

the "splitted" translation serves as a "sourcemap",
it has the correct positions of sentence-parts,
but the translation has worse quality,
because sentences are broken into sentence-parts.

the "joined" translation provides the translated sentences,
with better quality than the "splitted" translation,
but the locations of sentence-parts are lost.

currently, we align the two translations with a "character diff":

```sh
git diff --word-diff=color --word-diff-regex=. --no-index \
  $(readlink -f translation.joined.txt) \
  $(readlink -f translation.splitted.txt) |
sed -E $'s/\e\[32m.*?\e\[m//g; s/\e\\[[0-9;:]*[a-zA-Z]//g' |
tail -n +6 >translation.aligned.txt
```



## related

- [produce sourcemap of translation argos-translate#372](https://github.com/argosopentech/argos-translate/issues/372)
- [Prohibit the translation of pieces of text in Google Translate](https://webapps.stackexchange.com/questions/52668/prohibit-the-translation-of-pieces-of-text-in-google-translate/154694#154694)



### similar projects

- [argos-translate](https://github.com/argosopentech/argos-translate) - Open-source offline translation library written in Python
  - [argos-translate-files](https://github.com/LibreTranslate/argos-translate-files)
  - [argos-translate-html](https://github.com/argosopentech/translate-html) - too simple, no merging of "splitted" and "joined" translations
- [subtitlestranslator.com](https://subtitlestranslator.com/en/translate.php)
