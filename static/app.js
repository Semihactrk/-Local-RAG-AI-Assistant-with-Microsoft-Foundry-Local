const themeToggle = document.getElementById("themeToggle");

function currentTheme() {
  return (
    document.documentElement.getAttribute("data-theme") ||
    (window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light")
  );
}

function updateThemeIcon() {
  themeToggle.textContent = currentTheme() === "dark" ? "☀️" : "🌙";
}

themeToggle.addEventListener("click", () => {
  const next = currentTheme() === "dark" ? "light" : "dark";
  document.documentElement.setAttribute("data-theme", next);
  localStorage.setItem("theme", next);
  updateThemeIcon();
});

updateThemeIcon();

const chat = document.getElementById("chat");
const emptyState = document.getElementById("emptyState");
const composer = document.getElementById("composer");
const question = document.getElementById("question");
const sendBtn = document.getElementById("sendBtn");

function scrollToBottom() {
  chat.scrollTop = chat.scrollHeight;
}

function addMessage(role, text, extra = {}) {
  emptyState.remove();

  const msg = document.createElement("div");
  msg.className = `msg ${role}`;

  const bubble = document.createElement("div");
  bubble.className = "bubble";
  if (extra.notFound) bubble.classList.add("not-found");
  if (extra.error) bubble.classList.add("error");
  bubble.textContent = text;
  msg.appendChild(bubble);

  if (role === "assistant" && !extra.error) {
    const meta = document.createElement("div");
    meta.className = "meta-row";

    if (typeof extra.seconds === "number") {
      const time = document.createElement("span");
      time.className = "meta-time";
      time.textContent = `${extra.seconds}s`;
      meta.appendChild(time);
    }
    (extra.sources || []).forEach((src) => {
      const chip = document.createElement("span");
      chip.className = "source-chip";
      chip.textContent = `📄 ${src}`;
      meta.appendChild(chip);
    });
    if (meta.childNodes.length) msg.appendChild(meta);
  }

  chat.appendChild(msg);
  scrollToBottom();
  return msg;
}

function showTyping() {
  emptyState.remove?.();
  const msg = document.createElement("div");
  msg.className = "msg assistant";
  msg.id = "typingMsg";
  msg.innerHTML = `<div class="bubble typing"><span></span><span></span><span></span></div>`;
  chat.appendChild(msg);
  scrollToBottom();
}

function hideTyping() {
  document.getElementById("typingMsg")?.remove();
}

async function ask(q) {
  addMessage("user", q);
  showTyping();
  sendBtn.disabled = true;

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q }),
    });
    const data = await res.json();
    hideTyping();

    if (!res.ok) {
      addMessage("assistant", data.error || "An error occurred.", { error: true });
      return;
    }

    addMessage("assistant", data.answer, {
      seconds: data.seconds,
      sources: data.sources,
      notFound: data.skipped_llm && data.sources.length === 0,
    });
  } catch (err) {
    hideTyping();
    addMessage("assistant", "Couldn't reach the server. Make sure the Flask server is running.", { error: true });
  } finally {
    sendBtn.disabled = false;
    question.focus();
  }
}

composer.addEventListener("submit", (e) => {
  e.preventDefault();
  const q = question.value.trim();
  if (!q) return;
  question.value = "";
  question.style.height = "auto";
  ask(q);
});

question.addEventListener("keydown", (e) => {
  if (e.key === "Enter" && !e.shiftKey) {
    e.preventDefault();
    composer.requestSubmit();
  }
});

question.addEventListener("input", () => {
  question.style.height = "auto";
  question.style.height = Math.min(question.scrollHeight, 160) + "px";
});
