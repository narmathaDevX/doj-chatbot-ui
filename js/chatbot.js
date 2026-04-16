let currentMode = "strict";

function setMode(mode) {
    currentMode = mode;

    document.getElementById("strictBtn").classList.remove("active");
    document.getElementById("extendedBtn").classList.remove("active");

    if (mode === "strict") {
        document.getElementById("strictBtn").classList.add("active");
    } else {
        document.getElementById("extendedBtn").classList.add("active");
    }
}

async function sendMessage() {
    const input = document.getElementById("userInput");
    const chatBox = document.getElementById("chatBox");

    const userText = input.value.trim();
    if (userText === "") return;

    // USER MESSAGE
    const userMessage = document.createElement("div");
    userMessage.className = "message user";
    userMessage.innerHTML = `
        ${escapeHTML(userText)}
        <span class="time">${getTime()}</span>
    `;
    chatBox.appendChild(userMessage);

    input.value = "";
    chatBox.scrollTop = chatBox.scrollHeight;

    // TYPING
    const typing = document.createElement("div");
    typing.className = "message bot typing";
    typing.innerText = "Typing...";
    chatBox.appendChild(typing);
    chatBox.scrollTop = chatBox.scrollHeight;

    try {
        const response = await fetch("http://127.0.0.1:5000/chat", {
            method: "POST",
            headers: {
                "Content-Type": "application/json"
            },
            body: JSON.stringify({
                message: userText,
                mode: currentMode
            })
        });

        const data = await response.json();
        typing.remove();

        const botMessage = document.createElement("div");
        botMessage.className = "message bot";
        botMessage.innerHTML = `
            ${formatResponse(data.response)}
            <span class="time">${getTime()}</span>
        `;

        chatBox.appendChild(botMessage);
        chatBox.scrollTop = chatBox.scrollHeight;

    } catch (error) {
        typing.innerText = "Error connecting to server.";
    }
}

function formatResponse(text) {
    return escapeHTML(text).replace(/\n/g, "<br>");
}

function escapeHTML(str) {
    return str.replace(/[&<>"']/g, function (match) {
        const escape = {
            "&": "&amp;",
            "<": "&lt;",
            ">": "&gt;",
            '"': "&quot;",
            "'": "&#039;"
        };
        return escape[match];
    });
}

function getTime() {
    const now = new Date();
    return now.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
}

function handleKey(event) {
    if (event.key === "Enter") {
        sendMessage();
    }
}