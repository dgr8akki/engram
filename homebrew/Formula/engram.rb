class Engram < Formula
  desc "Local semantic knowledge base with MCP integration for AI coding tools"
  homepage "https://github.com/dgr8akki/engram"
  # Update url + sha256 when you cut a release tag
  url "https://github.com/dgr8akki/engram/archive/refs/tags/v0.1.0.tar.gz"
  sha256 "REPLACE_WITH_SHA256_AFTER_TAGGING"
  license "MIT"
  head "https://github.com/dgr8akki/engram.git", branch: "main"

  depends_on "python@3.12"

  # Generate resource blocks with:
  #   brew update-python-resources Formula/engram.rb
  # or manually:
  #   pip download -r requirements.txt -d /tmp/engram-wheels --no-deps
  #   for each wheel: shasum -a 256 <wheel> and find its PyPI url

  resource "mcp" do
    url "https://files.pythonhosted.org/packages/source/m/mcp/mcp-1.3.0.tar.gz"
    sha256 "REPLACE"
  end

  resource "sentence-transformers" do
    url "https://files.pythonhosted.org/packages/source/s/sentence-transformers/sentence_transformers-3.3.1.tar.gz"
    sha256 "REPLACE"
  end

  resource "sqlite-vec" do
    url "https://files.pythonhosted.org/packages/source/s/sqlite-vec/sqlite_vec-0.1.6.tar.gz"
    sha256 "REPLACE"
  end

  resource "PyYAML" do
    url "https://files.pythonhosted.org/packages/source/P/PyYAML/PyYAML-6.0.2.tar.gz"
    sha256 "REPLACE"
  end

  resource "click" do
    url "https://files.pythonhosted.org/packages/source/c/click/click-8.1.8.tar.gz"
    sha256 "REPLACE"
  end

  resource "numpy" do
    url "https://files.pythonhosted.org/packages/source/n/numpy/numpy-2.0.2.tar.gz"
    sha256 "REPLACE"
  end

  resource "fastapi" do
    url "https://files.pythonhosted.org/packages/source/f/fastapi/fastapi-0.111.1.tar.gz"
    sha256 "REPLACE"
  end

  resource "uvicorn" do
    url "https://files.pythonhosted.org/packages/source/u/uvicorn/uvicorn-0.30.6.tar.gz"
    sha256 "REPLACE"
  end

  resource "httpx" do
    url "https://files.pythonhosted.org/packages/source/h/httpx/httpx-0.27.2.tar.gz"
    sha256 "REPLACE"
  end

  def install
    # Install everything into a private virtualenv under libexec
    # so Engram's deps don't pollute the user's Python environment
    venv = virtualenv_create(libexec, "python3.12")
    venv.pip_install resources
    venv.pip_install buildpath

    # Copy runtime files into libexec
    libexec.install Dir["*.py", "*.yaml", "skill", "scripts"]

    # Write the engram wrapper pointing to our venv python
    (bin/"engram").write <<~BASH
      #!/bin/bash
      exec "#{libexec}/bin/python3" "#{libexec}/engram_cli.py" "$@"
    BASH
  end

  def post_install
    # Initialise the database and wire up MCP + skill + hooks
    # Runs silently; failures are non-fatal (user may not have any AI tools yet)
    system bin/"engram", "init" rescue nil
    system bin/"engram", "install" rescue nil
  end

  def caveats
    <<~EOS
      Engram has been installed and configured.

      If MCP / skill / hooks were not set up automatically, run:
        engram install

      To start the HTTP server (port 7823):
        engram serve

      Database location:
        #{var}/engram/engram.db
    EOS
  end

  test do
    system bin/"engram", "--help"
  end
end
