@ECHO OFF

set SOURCEDIR=.
set BUILDDIR=_build

if "%SPHINXBUILD%" == "" (
    set SPHINXBUILD=sphinx-build
)

if "%1" == "" goto help

%SPHINXBUILD% -M %1 %SOURCEDIR% %BUILDDIR%
goto end

:help
ECHO.Please use `make.bat ^<target^>` where ^<target^> is one of
ECHO.  html      to build the HTML documentation
ECHO.  clean     to remove the built documentation

:end
