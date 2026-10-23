const button = document.getElementById("helloButton");
const message = document.getElementById("message");

button.addEventListener("click", function() {
    message.textContent = "こんにちは！JavaScriptが動きました！";
});