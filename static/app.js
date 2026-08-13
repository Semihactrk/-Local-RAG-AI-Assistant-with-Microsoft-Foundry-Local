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
const composer = document.getElementById("composer");
const question = document.getElementById("question");
const sendBtn = document.getElementById("sendBtn");
const newConvBtn = document.getElementById("newConvBtn");
const convList = document.getElementById("convList");

const introCardHTML = document.getElementById("emptyState").outerHTML;
let currentConversationId = null;

function scrollToBottom() {
  chat.scrollTop = chat.scrollHeight;
}

function showIntroCard() {
  chat.innerHTML = introCardHTML;
}

function addMessage(role, text, extra = {}) {
  document.getElementById("emptyState")?.remove();

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
  document.getElementById("emptyState")?.remove();
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

function setActiveConversation(id) {
  convList.querySelectorAll(".conv-item").forEach((el) => {
    el.classList.toggle("active", el.dataset.id === String(id));
  });
}

function addConversationToSidebar(id, title) {
  convList.querySelector(".sidebar-empty")?.remove();
  const li = document.createElement("li");
  li.className = "conv-item active";
  li.dataset.id = id;
  li.textContent = title;
  convList.prepend(li);
  setActiveConversation(id);
}

async function loadConversation(id) {
  try {
    const res = await fetch(`/api/conversations/${id}`);
    const data = await res.json();
    if (!res.ok) return;

    chat.innerHTML = "";
    (data.messages || []).forEach((m) => {
      if (m.role === "user") {
        addMessage("user", m.content);
      } else {
        addMessage("assistant", m.content, {
          seconds: m.seconds,
          sources: m.sources,
          notFound: !m.sources || m.sources.length === 0,
        });
      }
    });
    if (!data.messages || data.messages.length === 0) showIntroCard();

    currentConversationId = id;
    setActiveConversation(id);
  } catch (err) {
    // Server unreachable -- leave the current view as-is.
  }
}

newConvBtn.addEventListener("click", () => {
  currentConversationId = null;
  showIntroCard();
  setActiveConversation(null);
  question.focus();
});

convList.addEventListener("click", (e) => {
  const item = e.target.closest(".conv-item");
  if (!item) return;
  loadConversation(item.dataset.id);
});

async function ask(q) {
  addMessage("user", q);
  showTyping();
  sendBtn.disabled = true;

  try {
    const res = await fetch("/api/ask", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ question: q, conversation_id: currentConversationId }),
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
      notFound: data.sources.length === 0,
    });

    if (data.is_new_conversation) {
      addConversationToSidebar(data.conversation_id, data.title);
    }
    currentConversationId = data.conversation_id;
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
