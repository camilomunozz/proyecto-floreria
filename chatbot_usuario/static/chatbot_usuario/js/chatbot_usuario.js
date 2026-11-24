
document.addEventListener("DOMContentLoaded", function () {

    // ==========================================
    // ELEMENTOS DEL CHATBOT
    // ==========================================

    const toggleButton = document.getElementById("chatbot-toggle");
    const closeButton = document.getElementById("chatbot-close");
    const chatWindow = document.getElementById("chatbot-window");
    const chatForm = document.getElementById("chatbot-form");
    const chatInput = document.getElementById("chatbot-input");
    const chatSend = document.getElementById("chatbot-send");
    const messagesContainer = document.getElementById("chatbot-messages");

    // Evitar errores si el widget no está presente
    if (
        !toggleButton ||
        !closeButton ||
        !chatWindow ||
        !chatForm ||
        !chatInput ||
        !chatSend ||
        !messagesContainer
    ) {
        return;
    }

    const API_URL = "/chatbot/api/chat/";

    let isSending = false;

    // ==========================================
    // ABRIR Y CERRAR CHAT
    // ==========================================

    function toggleChat(open) {
        chatWindow.hidden = !open;

        toggleButton.setAttribute(
            "aria-expanded",
            String(open)
        );

        if (open) {
            chatInput.focus();
        }
    }

    toggleButton.addEventListener("click", function () {
        toggleChat(chatWindow.hidden);
    });

    closeButton.addEventListener("click", function () {
        toggleChat(false);
    });

    // ==========================================
    // AGREGAR MENSAJES
    // ==========================================

    function addMessage(message, sender) {
        const messageElement = document.createElement("div");

        messageElement.classList.add(
            "chatbot-message",
            sender === "user"
                ? "chatbot-message-user"
                : "chatbot-message-bot"
        );

        // Mostrar el contenido como texto seguro
        messageElement.textContent = message;

        messagesContainer.appendChild(messageElement);

        messagesContainer.scrollTop =
            messagesContainer.scrollHeight;

        return messageElement;
    }

    // ==========================================
    // INDICADOR DE RESPUESTA
    // ==========================================

    function showTypingIndicator() {
        const indicator = document.createElement("div");

        indicator.classList.add(
            "chatbot-message",
            "chatbot-message-bot",
            "chatbot-message-loading"
        );

        indicator.textContent = "FlowerView está escribiendo...";

        indicator.setAttribute("aria-label", "Esperando respuesta");

        messagesContainer.appendChild(indicator);

        messagesContainer.scrollTop =
            messagesContainer.scrollHeight;

        return indicator;
    }

    // ==========================================
    // ESTADO DEL FORMULARIO
    // ==========================================

    function setSendingState(sending) {
        isSending = sending;

        chatInput.disabled = sending;
        chatSend.disabled = sending;

        chatForm.setAttribute(
            "aria-busy",
            String(sending)
        );

        chatSend.textContent = sending ? "…" : "➤";
    }

    // ==========================================
    // CONEXIÓN CON DJANGO Y GEMINI
    // ==========================================

    async function sendMessage(message) {

        const csrfToken = chatForm.querySelector(
            '[name="csrfmiddlewaretoken"]'
        )?.value;

        if (!csrfToken) {
            addMessage(
                "No pudimos validar la solicitud. Recarga la página e inténtalo nuevamente.",
                "bot"
            );
            return;
        }

        const typingIndicator = showTypingIndicator();

        setSendingState(true);

        try {

            const response = await fetch(API_URL, {
                method: "POST",

                headers: {
                    "Content-Type": "application/json",
                    "X-CSRFToken": csrfToken
                },

                credentials: "same-origin",

                body: JSON.stringify({
                    mensaje: message
                })
            });

            const data = await response.json();

            // Comprobar errores del servidor
            if (!response.ok) {
                throw new Error(
                    data.error ||
                    "No pudimos procesar tu mensaje."
                );
            }

            // Comprobar respuesta de Gemini
            if (
                typeof data.respuesta !== "string" ||
                !data.respuesta.trim()
            ) {
                throw new Error(
                    "El asistente no devolvió una respuesta."
                );
            }

            addMessage(data.respuesta, "bot");

        } catch (error) {

            console.error(
                "Error en el chatbot FlowerView:",
                error
            );

            addMessage(
                error.message ||
                "No pudimos conectar con nuestro asistente. Inténtalo nuevamente.",
                "bot"
            );

        } finally {

            // Eliminar indicador de escritura
            typingIndicator.remove();

            // Habilitar nuevamente el formulario
            setSendingState(false);

            chatInput.focus();
        }
    }

    // ==========================================
    // ENVIAR MENSAJE
    // ==========================================

    chatForm.addEventListener("submit", function (event) {

        event.preventDefault();

        // Evitar solicitudes simultáneas
        if (isSending) return;

        const message = chatInput.value.trim();

        if (!message) return;

        if (message.length > 1000) {
            addMessage(
                "Tu mensaje supera el límite de 1000 caracteres.",
                "bot"
            );
            return;
        }

        // Mostrar mensaje del cliente
        addMessage(message, "user");

        // Limpiar campo
        chatInput.value = "";

        // Consultar Gemini
        sendMessage(message);

    });

});
