import { config } from './config.js';

/**
 * Initialize the chat toggle functionality
 */
export function initChatToggle() {
    const toggleButton = document.getElementById('toggle-chat-source');
    const eventLog = document.getElementById('event-log');
    const twitchChatContainer = document.getElementById('twitch-chat-container');
    const messageInput = document.querySelector('.message-input-container');

    if (!toggleButton || !eventLog || !twitchChatContainer) return;

    // Initialize config values if not set
    config.isTwitchChatActive = config.isTwitchChatActive || false;

    // The iframe is already in the HTML, so consider it loaded
    config.twitchChatLoaded = true;

    // Set up event listener for toggle button
    toggleButton.addEventListener('click', () => {
        config.isTwitchChatActive = !config.isTwitchChatActive;

        if (config.isTwitchChatActive) {
            // Switch to Twitch chat
            eventLog.style.display = 'none';
            twitchChatContainer.style.display = 'block';
            toggleButton.innerHTML = '<span class="toggle-icon">⇄</span> Switch to Admin Chat';
            toggleButton.classList.add('twitch-active');

            // Hide message input when viewing Twitch chat
            if (messageInput) messageInput.style.display = 'none';
        } else {
            // Switch to custom chat
            eventLog.style.display = 'block';
            twitchChatContainer.style.display = 'none';
            toggleButton.innerHTML = '<span class="toggle-icon">⇄</span> Switch to Twitch Chat';
            toggleButton.classList.remove('twitch-active');

            // Show message input when viewing custom chat
            if (messageInput) messageInput.style.display = 'flex';

            // Scroll to bottom when switching back
            import('./scrolling.js').then(scrollModule => {
                scrollModule.scrollToBottom();
            });
        }
    });
}
