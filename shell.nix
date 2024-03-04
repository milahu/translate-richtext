{
  pkgs ? import <nixpkgs> {}
}:

let

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

    tree-sitter-languages = pkgs.python3.pkgs.callPackage ./nix/tree-sitter-languages/tree-sitter-languages.nix { };

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
