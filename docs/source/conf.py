"""Sphinx configuration for the PyTimeTag documentation."""

from datetime import datetime

project = "PyTimeTag"
author = "Hwaipy"
copyright = f"{datetime.now().year}, {author}"
release = "3.0.6"
version = release

extensions = [
    "sphinx.ext.autodoc",
    "sphinx.ext.autosummary",
    "sphinx.ext.napoleon",
    "sphinx.ext.viewcode",
    "sphinx.ext.intersphinx",
    "autoapi.extension",
]

templates_path = ["_templates"]
exclude_patterns = ["_build", "Thumbs.db", ".DS_Store"]

language = "en"
locale_dirs = ["locale/"]
gettext_compact = False

autosummary_generate = True
autodoc_member_order = "bysource"
autodoc_typehints = "description"
napoleon_google_docstring = True
napoleon_numpy_docstring = True

autoapi_type = "python"
autoapi_dirs = ["../../pytimetag"]
autoapi_root = "api"
autoapi_member_order = "bysource"
autoapi_keep_files = False
autoapi_options = [
    "members",
    "undoc-members",
    "show-inheritance",
    "show-module-summary",
]

html_theme = "furo"
html_title = "PyTimeTag Documentation"
html_static_path = ["_static"]

intersphinx_mapping = {
    "python": ("https://docs.python.org/3", None),
    "numpy": ("https://numpy.org/doc/stable/", None),
}