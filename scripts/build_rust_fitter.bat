@echo off
setlocal enabledelayedexpansion

set ROOT_DIR=%~dp0..
cargo build --release --manifest-path "%ROOT_DIR%\rust\manic_fitter\Cargo.toml" || exit /b 1
copy /Y "%ROOT_DIR%\rust\manic_fitter\target\release\manic_fitter.dll" "%ROOT_DIR%\src\manic\processors\manic_fitter.dll" || exit /b 1
echo Built and installed %ROOT_DIR%\src\manic\processors\manic_fitter.dll
exit /b 0
