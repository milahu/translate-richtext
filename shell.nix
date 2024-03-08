{
  pkgs ? import <nixpkgs> {}
}:

let

  tree-sitter-html-src = pkgs.fetchFromGitHub {
    repo = "tree-sitter-html";
    /*
    owner = "tree-sitter";
    # https://github.com/tree-sitter/tree-sitter-html/pull/89
    rev = "8801a68dacfd4a2f6e6c3b7c9adab551a06b267c";
    hash = "sha256-7VYLkr0CnPvWAac/sg7dXw6FuOZ6Xwof2GqRuDu3NuM=";
    */
    owner = "milahu";
    # https://github.com/milahu/tree-sitter-html/tree/pulls-89-and-90
    rev = "dffe3c09470a695819c0cce58b2acbbb6f83fcd9";
    hash = "sha256-VK2dirxYhImlvopz/s2BCZMQHW6C7xP6XGCOrazNvPQ=";
  };

  extraPythonPackages = rec {

    cdp-socket = pkgs.python3.pkgs.callPackage ./nix/cdp-socket.nix {};

    # error: Package ‘python3.10-selenium-driverless-1.6.3.3’ has an unfree license (‘cc-by-nc-sa-40’), refusing to evaluate.
    selenium-driverless = pkgs.python3.pkgs.callPackage ./nix/selenium-driverless.nix {
      cdp-socket = pkgs.python3.pkgs.callPackage ./nix/cdp-socket.nix {};
      selenium = pkgs.python3.pkgs.callPackage ./nix/selenium.nix { };
    };

    # fix: ModuleNotFoundError: No module named 'selenium.webdriver.common.devtools'
    # https://github.com/milahu/nixpkgs/issues/20
    selenium = pkgs.python3.pkgs.callPackage ./nix/selenium.nix { };

    tree-sitter-languages = pkgs.python3.pkgs.callPackage ./nix/tree-sitter-languages/tree-sitter-languages.nix {
      tree-sitter-grammars = pkgs.tree-sitter-grammars // {
        # https://github.com/tree-sitter/tree-sitter-html/pull/89
        # add leading and trailing whitespace to text nodes
        tree-sitter-html = pkgs.tree-sitter-grammars.tree-sitter-html.overrideAttrs (oldAttrs: {
          src = tree-sitter-html-src;
        });
      };
    };
  };

  python = pkgs.python3.withPackages (pythonPackages:
  (with pythonPackages; [
    tree-sitter
    argostranslate
    translatehtml
    /*
    requests
    magic # libmagic
    chardet
    charset-normalizer
    guessit # parse video filenames
    #playwright
    setuptools # pkg_resources for playwright-stealth
    #pyppeteer pyppeteer-stealth # puppeteer # old
    #kaitaistruct
    #sqlglot
    # distributed processing
    # ray is too complex, has only binary package in nixpkgs https://github.com/NixOS/nixpkgs/pull/194357
    #ray
    # https://github.com/tomerfiliba-org/rpyc
    #rpyc
    aiohttp
    aiohttp-socks # https://stackoverflow.com/a/76656557/10440128
    aiodns # make aiohttp faster
    brotli # make aiohttp faster
    natsort
    #pycdlib
    psutil
    pyparsing
    cryptography
    nest-asyncio
    mitmproxy
    proxy-py
    pproxy
    # FIXME passlib.exc.InternalBackendError: crypt.crypt() failed for unknown reason; passlib recommends running `pip install bcrypt` for general bcrypt support.(config=<hash <class 'str'> value omitted>, secret=<hash <class 'bytes'> value omitted>)
    #bcrypt
    pysubs2
    lxml # xhtml parser
    beautifulsoup4 # html parser
    fritzconnection # fritzbox client
    #selenium
    */
  ])
  ++
  (with extraPythonPackages; [
    selenium-driverless
    cdp-socket
    tree-sitter-languages
  ])
  );

  chromium = pkgs.ungoogled-chromium;

in

pkgs.mkShell rec {

  TREE_SITTER_HTML_SRC = tree-sitter-html-src;

  buildInputs = (with pkgs; [
  ]) ++ [
    python
  ]
  ++
  (with extraPythonPackages; [
    selenium-driverless
    cdp-socket
    tree-sitter-languages
  ]);

}
