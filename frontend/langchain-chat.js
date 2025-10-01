/**
 * LangChain RAG Chat Integration for BudgetWise
 * This script provides a more advanced and structured RAG implementation
 * using LangChain on the backend for improved financial query processing.
 */

const LANGCHAIN_API_BASE = window.BUDGETWISE_API_BASE || "http://127.0.0.1:5001";

// Initialize the LangChain Chat
(function initLangChainChat() {
  console.log("LangChain RAG Chat script loaded");

  // Find UI elements with fallbacks for both regular and langchain-specific selectors
  const $messages = document.getElementById('langchain-chat-messages') ||
    document.getElementById('chat-messages');
  const $form = document.getElementById('langchain-chat-form') ||
    document.getElementById('chat-form');
  const $input = document.getElementById('langchain-chat-text') ||
    document.getElementById('chat-text');
  const $buildBtn = document.getElementById('langchain-build-index') ||
    document.getElementById('build-index');

  // Debug elements
  console.log("LangChain Chat elements:", { messages: $messages, form: $form, input: $input, buildBtn: $buildBtn });

  // Early return if required elements are missing
  if (!$messages) {
    console.error("Chat messages element not found!");
    return;
  }

  if (!$form) {
    console.error("Chat form not found!");
    return;
  }

  if (!$input) {
    console.error("Chat input field not found!");
    return;
  }

  if (!$buildBtn) {
    console.error("Build index button not found!");
    return;
  }

  console.log("All required LangChain chat elements found!");

  // Helper function to get JWT token
  function token() { return localStorage.getItem('token'); }

  // Add message to chat UI
  function renderMarkdown(md) {
    // Minimal safe Markdown renderer for headings, bold, code, lists, and line breaks
    let html = md
      .replace(/&/g, '&amp;').replace(/</g, '&lt;').replace(/>/g, '&gt;')
      .replace(/^###\s+(.*$)/gim, '<h3>$1</h3>')
      .replace(/^##\s+(.*$)/gim, '<h2>$1</h2>')
      .replace(/^#\s+(.*$)/gim, '<h1>$1</h1>')
      .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
      .replace(/\*(.*?)\*/g, '<em>$1</em>')
      .replace(/`([^`]+)`/g, '<code>$1</code>')
      .replace(/^-\s+(.*)$/gim, '<li>$1</li>')
      .replace(/(<li>.*<\/li>)/gims, '<ul>$1</ul>')
      .replace(/\n\n/g, '<br/><br/>');
    return html;
  }

  function addMsg(role, text, opts = { markdown: true }) {
    const wrap = document.createElement('div');
    wrap.className = `msg ${role}`;
    const content = opts.markdown ? renderMarkdown(text) : text.replace(/[&<>]/g, c => ({ '&': '&amp;', '<': '&lt;', '>': '&gt;' }[c]));
    wrap.innerHTML = `<div class="bubble">${content}</div>`;
    $messages.appendChild(wrap);
    $messages.scrollTop = $messages.scrollHeight;
  }

  function showTyping() {
    const el = document.createElement('div');
    el.className = 'msg bot typing';
    el.innerHTML = '<div class="bubble"><span class="dots"><span></span><span></span><span></span></span></div>';
    $messages.appendChild(el);
    $messages.scrollTop = $messages.scrollHeight;
    return el;
  }

  // Build LangChain index
  async function buildIndex() {
    console.log("Building LangChain index...");
    addMsg('bot', 'Building LangChain index... This may take a moment.');

    try {
      const res = await fetch(`${LANGCHAIN_API_BASE}/chatbot/langchain/build`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ reindex: true })
      });

      console.log("LangChain build index response status:", res.status);
      const data = await res.json();
      console.log("LangChain build index response data:", data);

      if (!res.ok) {
        const errMsg = data?.error || data?.message || `LangChain index build failed (${res.status})`;
        console.error("LangChain build detailed error:", { status: res.status, body: data });
        if (res.status === 429) {
          addMsg('bot', `Rate limited while building index. Please wait 10–20s and try again. Details: ${errMsg}`);
        }
        throw new Error(errMsg);
      }

      addMsg('bot', `Success! LangChain index built with ${data.indexed ?? 'N/A'} items. You can now ask more nuanced questions about your finances.`);

      // Also fetch and display stats
      await fetchIndexStats();
    } catch (e) {
      console.error("LangChain index build error:", e);
      addMsg('bot', `Index error: ${e.message}. If this is a rate limit (429), wait and retry.`);
    }
  }

  // Fetch LangChain index stats
  async function fetchIndexStats() {
    try {
      const res = await fetch(`${LANGCHAIN_API_BASE}/chatbot/langchain/stats`, {
        headers: {
          'Authorization': `Bearer ${token()}`
        }
      });

      if (!res.ok) return;

      const stats = await res.json();
      console.log("LangChain index stats:", stats);

      // If we have enough stats, show a summary
      if (stats.total_documents > 0) {
        const userCount = Object.keys(stats.users || {}).length;
        const categories = Object.keys(stats.categories || {}).length;

        addMsg('bot',
          `Index statistics:\n` +
          `- ${stats.total_documents} total transactions indexed\n` +
          `- ${userCount} users in index\n` +
          `- ${categories} unique categories\n` +
          `- ${Math.round(stats.index_size_kb || 0)}KB index size`
        );
      }
    } catch (e) {
      console.error("Error fetching index stats:", e);
    }
  }

  // Check authentication
  function checkAuth() {
    const token = localStorage.getItem('token');
    if (!token) {
      addMsg('bot', 'Error: You need to log in first.');
      console.error('No authentication token found');
      return false;
    }
    return true;
  }

  // Add button handler for build index
  $buildBtn.addEventListener('click', (e) => {
    e.preventDefault();
    console.log("Build LangChain index button clicked");
    if (!checkAuth()) return;
    buildIndex();
  });

  // Find the ask button
  const $askBtn = document.getElementById('langchain-ask-btn') ||
    document.getElementById('ask-btn');

  // Check if ask button exists
  if (!$askBtn) {
    console.error("Ask button not found!");
  } else {
    console.log("Ask button found, adding handler");

    // Handle ask button click
    $askBtn.addEventListener('click', handleQuery);
  }

  // Add clear memory button handler
  const $clearMemoryBtn = document.getElementById('clear-memory-btn');
  if ($clearMemoryBtn) {
    $clearMemoryBtn.addEventListener('click', async (e) => {
      e.preventDefault();
      console.log("Clear memory button clicked");
      if (!checkAuth()) return;

      try {
        addMsg('bot', 'Clearing conversation history...');

        const res = await fetch(`${LANGCHAIN_API_BASE}/chatbot/langchain/clear-memory`, {
          method: 'POST',
          headers: {
            'Authorization': `Bearer ${token()}`,
            'Content-Type': 'application/json'
          }
        });

        const data = await res.json();
        console.log("Clear memory response:", data);

        if (res.ok) {
          addMsg('bot', '🔄 Conversation history cleared! I\'ll start fresh from here. Feel free to ask me anything about your finances!');
        } else {
          console.error("Clear memory failed:", data);
          addMsg('bot', `Failed to clear conversation history: ${data.message || data.error || 'Unknown error'}`);
        }
      } catch (e) {
        console.error("Error clearing memory:", e);
        addMsg('bot', `Error clearing conversation history: ${e.message}. Please make sure the server is running.`);
      }
    });
  } else {
    console.warn("Clear memory button not found");
  }

  // Add enter key handler to input field
  $input.addEventListener('keydown', (ev) => {
    if (ev.key === 'Enter') {
      ev.preventDefault();
      handleQuery();
    }
  });

  // Handle chat query
  async function handleQuery() {
    console.log("LangChain Ask button clicked");
    if (!checkAuth()) return;

    const q = $input.value.trim();
    if (!q) {
      console.log("Empty query, not sending");
      return;
    }

    addMsg('user', q);
    $input.value = '';

    try {
      console.log("Sending query to LangChain API:", q);
      const typingEl = showTyping();

      const res = await fetch(`${LANGCHAIN_API_BASE}/chatbot/langchain/query`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token()}`,
          'Content-Type': 'application/json'
        },
        body: JSON.stringify({ query: q, top_k: 8 })
      });

      console.log("LangChain API response status:", res.status);
      const data = await res.json();
      console.log("LangChain API response data:", data);

      // Remove typing indicator
      typingEl?.remove();

      if (!res.ok) {
        console.error("LangChain query detailed error:", { status: res.status, body: data });
        throw new Error(data.message || data.error || `Query failed (${res.status})`);
      }

      // Display the natural language answer
      const answer = data.answer || 'I couldn\'t generate an answer. Please try rephrasing your question.';
      addMsg('bot', answer);

      // Log matches for debugging (but don't display them)
      if (data.matches && data.matches.length > 0) {
        console.log(`Found ${data.matches.length} relevant transactions:`, data.matches);
      }
    } catch (e) {
      console.error("LangChain query error:", e);
      addMsg('bot', `Error: ${e.message}. Check the browser console for details.`);
    }
  }
})();