/**
 * Main JavaScript for Twitch Admin Panel
 * Handles real-time updates, state management, and UI interaction
 */

// Import modules
import { createMessageElement } from './message-processor.js';
import { config, filterMap } from './config.js';
import { setupScrollHandlers, scrollToBottom, shouldScrollToBottom } from './scrolling.js';
import { initChatToggle } from './twitch_chat.js';

// Global state management
const state = {
    messages: [],
    currentFilter: 'all',
    eventSource: null,
    isConnected: false,
    lastTimestamp: 0
};

// DOM elements cache
const elements = {
    eventLog: null,
    filterSelect: null,
    clearButton: null,
    deleteForm: {
        daysInput: null,
        button: null
    }
};

/**
 * Initialize the application when DOM is ready
 */
document.addEventListener('DOMContentLoaded', () => {
    console.log('Initializing Twitch Admin Panel');

    // Cache DOM elements
    elements.eventLog = document.getElementById('event-log');
    elements.filterSelect = document.getElementById('filter-select');
    elements.clearEmoteCacheButton = document.querySelector('button[data-action="clear_emote_cache"]');
    elements.deleteForm.daysInput = document.querySelector('input[type="number"]');
    elements.deleteForm.button = document.querySelector('button[data-action="delete"]');
    elements.refreshButton = document.querySelector('button[data-action="refresh"]');


    // Set up send message functionality
    elements.messageInput = document.getElementById('message-input');
    elements.sendButton = document.getElementById('send-message-btn');

    // Set up event listeners
    setupEventListeners();

    // Initialize the event source for real-time updates
    initEventSource();

    // Load initial messages
    fetchMessages();

    // Set up scroll handlers
    setupScrollHandlers();

    // Initial scroll to bottom
    scrollToBottom();

    initChatToggle();



});

/**
 * Set up event listeners
 */
function setupEventListeners() {
    // Filter select
    if (elements.filterSelect) {
        elements.filterSelect.addEventListener('change', (e) => {
            state.currentFilter = e.target.value;
            fetchMessages();
        });
    }

    // Refresh button
    if (elements.refreshButton) {
        elements.refreshButton.addEventListener('click', fetchMessages);
    }

    // Clear button
    if (elements.clearEmoteCacheButton) {
        elements.clearEmoteCacheButton.addEventListener('click', clearEmoteCache);
    }

    // Delete old messages button
    if (elements.deleteForm.button) {
        elements.deleteForm.button.addEventListener('click', deleteOldMessages);
    }

    if (elements.messageInput) {
        elements.messageInput.style.display = config.isTwitchChatActive ? 'none' : 'flex';
    }

    if (elements.messageInput && elements.sendButton) {
        // Function to send message
        function sendMessage() {
            const message = elements.messageInput.value.trim();
            if (message) {
                // Replace with your actual send message logic
                console.log('Sending message:', message);

                // Example implementation - adjust to your actual API
                fetch('/chat/send-message', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({message: message})
                }).then(response => {
                    if (!response.ok) {
                        throw new Error(`HTTP error: ${response.status}`);
                    }
                    elements.messageInput.value = ''; // Clear input after sending
                });
            }
        }


        // Send on button click
        elements.sendButton.addEventListener('click', sendMessage);

        // Also send on Enter key
        elements.messageInput.addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                sendMessage();
            }
        });
    }
}

/**
 * Initialize the EventSource connection for real-time updates
 */
function initEventSource() {
    // Close existing connection if any
    if (state.eventSource) {
        state.eventSource.close();
    }

    console.log('Initializing EventSource connection...');
    updateConnectionStatus('Connecting...');

    // Create new EventSource connection
    state.eventSource = new EventSource('/stream');

    // Handle connection open
    state.eventSource.onopen = () => {
        console.log('EventSource connection established');
        state.isConnected = true;
        state.reconnectAttempts = 0;
        updateConnectionStatus('Connected');
    };

    // Handle connection error
    state.eventSource.onerror = (error) => {
        console.error('EventSource error:', error);
        state.isConnected = false;
        updateConnectionStatus('Disconnected');

        // Attempt to reconnect after a delay if connection is closed
        if (state.eventSource.readyState === EventSource.CLOSED) {
            state.reconnectAttempts++;

            if (state.reconnectAttempts <= state.maxReconnectAttempts) {
                const delay = state.reconnectDelay * Math.min(state.reconnectAttempts, 3);
                updateConnectionStatus(`Reconnecting in ${delay/1000}s... (${state.reconnectAttempts}/${state.maxReconnectAttempts})`);

                setTimeout(() => {
                    console.log(`Attempting to reconnect... (${state.reconnectAttempts}/${state.maxReconnectAttempts})`);
                    initEventSource();
                }, delay);
            } else {
                updateConnectionStatus('Connection failed. Please refresh the page.');
            }
        }
    };

    // Handle standard messages (this is the key change)
    state.eventSource.onmessage = (event) => {
        try {
            const notification = JSON.parse(event.data);
            console.log('Notification received:', notification);

            // Check if this is a new message notification
            if (notification.action === 'new_message') {
                const messageType = notification.message_type;

                // If the message type matches our current filter or we're showing all
                if (state.currentFilter === 'all' || isMessageTypeMatch(messageType, state.currentFilter)) {
                    // Fetch the latest messages
                    fetchMessages(1);
                }
            } else if (notification.action === 'init') {
                console.log('EventSource initialized:', notification.message);
                updateConnectionStatus('Connected and ready');
            } else if (notification.action === 'error') {
                console.error('EventSource error notification:', notification.message);
                updateConnectionStatus('Error: ' + notification.message);
            }
        } catch (error) {
            console.error('Error processing event data:', error);
        }
    };
}

/**
 * Update the connection status in the UI
 */
function updateConnectionStatus(status) {
    const statusElement = document.getElementById('connection-status');
    if (statusElement) {
        // Set title attribute for accessibility/tooltip
        if (status.includes('Connected')) {
            statusElement.title = "Connected";
            statusElement.className = 'status-indicator connected';
        } else if (status.includes('Connecting') || status.includes('Reconnecting')) {
            statusElement.title = "Connecting...";
            statusElement.className = 'status-indicator connecting';
        } else {
            statusElement.title = "Not connected";
            statusElement.className = 'status-indicator';
        }
    }
}


/**
 * Check if a message type matches the current filter
 */
function isMessageTypeMatch(messageType, filter) {
    if (filter === 'all') return true;


    return filterMap[filter]?.includes(messageType) || false;
}


// Implementation of the load more function
config.loadMoreEntriesCallback = async function() {
    // If we have messages loaded already, increment the index
    const nextStartIndex = config.lastLoadedIndex + config.messagesPerLoad;

    // Call the existing fetchMessages function with the next batch of messages
    try {
        // Store the current message count before fetching
        const currentMessageCount = state.messages.length;

        // Call your existing fetch function with pagination parameters
        await fetchMessages(config.messagesPerLoad, nextStartIndex);

        // Check if we got any new messages
        const newMessageCount = state.messages.length;
        const messagesAdded = newMessageCount > currentMessageCount;

        if (messagesAdded) {
            // Update the last loaded index for next time
            config.lastLoadedIndex = nextStartIndex;
            return true; // We got messages, there might be more
        } else {
            return false; // No new messages, we've reached the end
        }
    } catch (error) {
        console.error('Error loading more messages:', error);
        return false; // Error occurred, don't try to load more right now
    }
};

/**
 * Fetch messages from the server API
 */
async function fetchMessages(count = 100, start = 0) {
    try {
        // Build API URL based on current filter
        let url = `/api/messages/recent?count=${count}&start=${start}`;

        // Add filter if not 'all'
        if (state.currentFilter !== 'all') {

            url += `&type=${filterMap[state.currentFilter]}`;
        }

        console.log(`Fetching messages from: ${url}`);

        const response = await fetch(url);
        if (!response.ok) {
            throw new Error(`HTTP error: ${response.status}`);
        }

        const messages = await response.json();
        console.log(`Received ${messages.length} messages`);

        // Update state
        if (start === 0 && count > 1) {
            // Replace all messages
            state.messages = messages;

            // Schedule scrolling for after DOM updates
            setTimeout(scrollToBottom, 100);
        } else {
            // Add new messages, avoiding duplicates
            const existingIds = new Set(state.messages.map(m => `${m.timestamp}-${m.content}`));
            const newMessages = messages.filter(m => !existingIds.has(`${m.timestamp}-${m.content}`));
            state.messages = [...newMessages, ...state.messages]
                .sort((a, b) => new Date(b.timestamp) - new Date(a.timestamp));
            if(start === 0) {
                // Schedule scrolling for after DOM updates
                setTimeout(scrollToBottom, 100);
            }
        }

        // Render the updated messages
        renderMessages();

    } catch (error) {
        console.error('Error fetching messages:', error);
    }
}




/**
 * Render messages in the event log
 */
function renderMessages() {
    const eventLog = document.getElementById('event-log');
    if (!eventLog) return;

    // Clear the event log first
    eventLog.innerHTML = '';

    if (state.messages.length === 0) {
        eventLog.innerHTML = '<div class="no-events">No events to display</div>';
        return;
    }

    // Get a copy of the messages array and reverse it
    // This puts oldest messages at the top and newest at the bottom
    const chronologicalMessages = [...state.messages].reverse();

    // Create elements for each message
    chronologicalMessages.forEach(message => {
        const messageElement = createMessageElement(message);
        eventLog.appendChild(messageElement);
    });
}


/**
 * Clear the event log
 */
function clearEmoteCache() {
    // Show loading indicator (optional)
    const statusElement = document.getElementById("cacheStatus");
    if (statusElement) {
        statusElement.textContent = "Clearing cache...";
    }

    // Call the API endpoint to clear the cache
    fetch('/api/clear_cache')
        .then(response => {
            if (!response.ok) {
                throw new Error(`Server responded with ${response.status}`);
            }
            return response.json();
        })
        .then(data => {
            console.log("Cache cleared successfully:", data);

            // Update UI with results
            if (statusElement) {
                statusElement.textContent = `Cache cleared: ${data.cleared_counts.total} items removed`;

                // Show detailed breakdown if needed
                const detailsElement = document.getElementById("cacheDetails");
                if (detailsElement) {
                    detailsElement.innerHTML = `
            <p>Twitch emotes: ${data.cleared_counts.twitch_emotes}</p>
            <p>BTTV emotes: ${data.cleared_counts.bttv_emotes}</p>
            <p>7TV emotes: ${data.cleared_counts.seventv_emotes}</p>
            <p>Commands: ${data.cleared_counts.commands}</p>
            <p>Emote metadata: ${data.cleared_counts.emote_metadata}</p>
          `;
                }
            }

            // If you're also maintaining a client-side cache
            window.emoteCache = {};
            localStorage.removeItem("emoteCache");
        })
        .catch(error => {
            console.error("Error clearing cache:", error);
            if (statusElement) {
                statusElement.textContent = `Error clearing cache: ${error.message}`;
            }
        });
}


/**
 * Delete old messages via API
 */
async function deleteOldMessages() {
    try {
        const days = elements.deleteForm.daysInput ? parseInt(elements.deleteForm.daysInput.value) || 30 : 30;

        console.log(`Deleting messages older than ${days} days...`);

        const response = await fetch(`/api/messages/delete?days=${days}`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`HTTP error: ${response.status}`);
        }

        const result = await response.json();
        console.log('Delete operation result:', result);

        // Show success message
        if (result.success) {
            const counts = result.deleted_counts || {};
            const total = counts.all || 0;
            alert(`Successfully deleted ${total} old messages.`);

            // Refresh messages
            fetchMessages();
        }

    } catch (error) {
        console.error('Error deleting messages:', error);
        alert(`Error: ${error.message}`);
    }
}

