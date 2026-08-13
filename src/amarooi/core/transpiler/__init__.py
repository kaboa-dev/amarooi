"""Target transpiler generators for the Amarooi framework."""

from amarooi.core.transpiler.base import BaseTargetTranspiler
from amarooi.core.transpiler.cobol_generator import CobolTranspiler
from amarooi.core.transpiler.csharp_generator import CSharpTranspiler
from amarooi.core.transpiler.go_generator import GoTranspiler
from amarooi.core.transpiler.js_generator import JavaScriptTranspiler

__all__ = [
    "BaseTargetTranspiler",
    "CobolTranspiler",
    "CSharpTranspiler",
    "GoTranspiler",
    "JavaScriptTranspiler",
]
