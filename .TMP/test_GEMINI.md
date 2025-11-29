ввод ключа:
$env:GEMINI_API_KEY = "MyAPIKeyHere"  

проверка ключа:
echo $env:GEMINI_API_KEY     

Запрос к gemini:

curl.exe -X POST "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash-image:generateContent?key=$($env:GEMINI_API_KEY)" `                                                                                >>   -H "Content-Type: application/json" `                                                                              >>   -d '{\"contents\":[{\"parts\":[{\"text\":\"ping\"}]}]}'
