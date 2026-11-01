@echo off
setlocal enabledelayedexpansion
pushd "%~dp0"
python run_benchmark.py %*
popd
