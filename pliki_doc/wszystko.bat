@echo off
for %%f in (*.docx) do (
    echo Przetwarzanie: %%f
    pandoc "%%f" -o "%%~nf.html" --mathjax -s --css=artykul.css --extract-media="%%~nf"
)
echo.
echo Gotowe! Wszystkie pliki zostały przetworzone.
pause