
// FARM DETAILS AND HISTORY
const farmForm = document.getElementById("farmForm");
const historyList = document.getElementById("historyList");

if (farmForm) {
    farmForm.addEventListener("submit", function(event) {
        event.preventDefault();

        const location = document.getElementById("location").value.trim();
        const soil = document.getElementById("soilType").value;
        const water = document.getElementById("water").value;
        const crop1 = document.getElementById("crop1").value.trim();
        const crop2 = document.getElementById("crop2").value.trim();

        const summary = document.getElementById("farmSummary");

        summary.textContent =
            `Farm: ${location} | Soil: ${soil} | Water: ${water} | Previous crops: ${crop1}${crop2 ? " and " + crop2 : ""}`;

        const item = document.createElement("div");
        item.className = "history-item";

        const details = document.createElement("span");
        details.textContent = `${location} · ${soil} · ${crop1}`;

        const date = document.createElement("small");
        date.textContent = new Date().toLocaleDateString();

        item.append(details, date);

        if (historyList.querySelector(".demo-note")) {
            historyList.innerHTML = "";
        }

        historyList.prepend(item);

        summary.scrollIntoView({ behavior: "smooth", block: "center" });
        alert("Sample farm report generated!");
    });
}

// DARK MODE
const themeToggle = document.getElementById("themeToggle");

if (themeToggle) {
    themeToggle.addEventListener("click", function() {
        document.body.classList.toggle("dark-mode");

        themeToggle.textContent =
            document.body.classList.contains("dark-mode") ? "☀️" : "🌙";
    });
}

// PLANT IMAGE PREVIEW
const leafUpload = document.getElementById("leafUpload");
const leafPreview = document.getElementById("leafPreview");
const leafMessage = document.getElementById("leafMessage");

if (leafUpload) {
    leafUpload.addEventListener("change", function() {
        const file = this.files[0];

        if (!file) return;

        if (!file.type.startsWith("image/")) {
            leafMessage.textContent = "Please select an image file.";
            leafPreview.style.display = "none";
            return;
        }

        const imageURL = URL.createObjectURL(file);
        leafPreview.src = imageURL;
        leafPreview.style.display = "block";
        leafMessage.textContent = "Image uploaded successfully. Preview only; no disease analysis performed.";
    });
}

// SMART IRRIGATION
const moistureSlider = document.getElementById("moistureSlider");

if (moistureSlider) {
    moistureSlider.addEventListener("input", function() {
        const value = Number(this.value);

        document.getElementById("moistureValue").textContent = value + "%";
        document.getElementById("moistureBar").style.width = value + "%";

        let status;

        if (value < 30) {
            status = "Low Moisture – Sample: Check watering needs";
        } else if (value < 70) {
            status = "Moderate Moisture – Sample";
        } else {
            status = "High Moisture – Sample: Check drainage";
        }

        document.getElementById("waterStatus").textContent = status;
    });
}

// AI ASSISTANT DEMO CHAT
const chatForm = document.getElementById("chatForm");
const chatInput = document.getElementById("chatInput");
const chatMessages = document.getElementById("chatMessages");

function addMessage(message, className) {
    const bubble = document.createElement("div");
    bubble.className = className;
    bubble.textContent = message;
    chatMessages.appendChild(bubble);
    chatMessages.scrollTop = chatMessages.scrollHeight;
}

function getDemoReply(question) {
    const q = question.toLowerCase();

    if (q.includes("soil") || q.includes("ph")) {
        return "Soil testing helps understand pH and nutrient levels. Please use a verified soil test for actual results.";
    }

    if (q.includes("water") || q.includes("irrigation")) {
        return "Irrigation depends on crop type, soil and moisture. Check actual field moisture before watering.";
    }

    if (q.includes("fertilizer") || q.includes("manure")) {
        return "Fertilizer choice should be based on a soil test and crop requirement. Consult an agricultural expert for dosage.";
    }

    if (q.includes("rice") || q.includes("crop")) {
        return "Crop selection depends on season, soil, water availability and local conditions. Check local agricultural guidance.";
    }

    if (q.includes("hello") || q.includes("hi")) {
        return "Hello! Welcome to Soil Verity. Ask me about soil, crops or irrigation.";
    }

    return "Thanks for your question! This is a demo assistant. Please consult your local agricultural officer for verified advice.";
}

if (chatForm) {
    chatForm.addEventListener("submit", function(event) {
        event.preventDefault();

        const question = chatInput.value.trim();

        if (!question) return;

        addMessage(question, "user-message");
        addMessage(getDemoReply(question), "bot-message");

        chatInput.value = "";
    });
}

// PDF REPORT
const downloadReport = document.getElementById("downloadReport");

if (downloadReport) {
    downloadReport.addEventListener("click", function() {
        window.print();
    });
}
