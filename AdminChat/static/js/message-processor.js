/**
 * Message Processor Module
 * Handles the rendering and processing of different message types
 */

// Import dependencies
import { parseAndRenderMessage } from './emote-handler.js';
import { addBadgesToElement } from './badge-handler.js';

/**
 * Create a DOM element for a message
 * @param {Object} message - The message object to render
 * @returns {HTMLElement} - The message DOM element
 */
export function createMessageElement(message) {
    const messageDiv = document.createElement('div');
    messageDiv.className = `event-item ${message.type || 'unknown'}-event`;

    // Add timestamp
    const time = new Date(message.timestamp);
    const timeDiv = document.createElement('div');
    timeDiv.className = 'event-time';
    timeDiv.textContent = time.toLocaleTimeString();
    messageDiv.appendChild(timeDiv);

    // Add message content based on type
    const renderFunctions = {
        'chat': renderChatMessage,
        'command': renderCommandMessage,
        'subscription': renderSubscriptionMessage,
        'sub': renderSubscriptionMessage,
        'redeem': renderRedeemMessage,
        'raid': renderRaidMessage,
        'admin': renderSystemMessage,
        'system': renderSystemMessage
    };

    const renderFunction = renderFunctions[message.type] || renderGenericMessage;
    renderFunction(message, messageDiv);

    return messageDiv;
}

/**
 * Format emotes object into Twitch format for emote parser
 * @param {Object|Array|String} emotes - Emotes in various formats
 * @returns {String} - Formatted emote string
 */
export function formatEmotesForParser(emotes) {
    // Handle empty/undefined emotes
    if (!emotes) return '';

    const parts = [];

    // Case 1: Object format from Twitch { emoteId: [{ start, end }, ...] }
    if (typeof emotes === 'object' && !Array.isArray(emotes)) {
        for (const [id, positions] of Object.entries(emotes)) {
            if (Array.isArray(positions)) {
                const posStr = positions
                    .filter(p => p && typeof p === 'object' && 'start' in p && 'end' in p)
                    .map(p => `${p.start}-${p.end}`)
                    .join(',');

                if (posStr) {
                    parts.push(`${id}:${posStr}`);
                }
            } else if (typeof positions === 'string') {
                // Handle case where positions might be a comma-separated string
                parts.push(`${id}:${positions}`);
            }
        }
    }
    // Case 2: Already formatted string "emoteId:start-end,start-end/emoteId:start-end"
    else if (typeof emotes === 'string' && emotes.includes(':')) {
        return emotes; // Already in the correct format
    }
    // Case 3: Array format [{ id, positions: [start-end, ...] }, ...]
    else if (Array.isArray(emotes)) {
        for (const emote of emotes) {
            if (emote && emote.id) {
                if (typeof emote.positions === 'string') {
                    parts.push(`${emote.id}:${emote.positions}`);
                } else if (Array.isArray(emote.positions)) {
                    const posStr = emote.positions.join(',');
                    if (posStr) {
                        parts.push(`${emote.id}:${posStr}`);
                    }
                }
            }
        }
    }

    return parts.join('/');
}

/**
 * Render message content with emote support
 * @param {HTMLElement} contentElement - The DOM element to render content into
 * @param {Object} message - The message object containing content and author data
 */
export function renderContentWithEmotes(contentElement, message) {
    if (!message.content) {
        contentElement.textContent = '(empty message)';
        return;
    }

    try {
        // Get emotes if available, or use empty object
        const emotes = (message.author && message.author.emotes) || {};
        // Format emotes for the parser
        const emoteString = formatEmotesForParser(emotes);
        // Parse and render message with emotes
        parseAndRenderMessage(contentElement, message.content, emoteString);
    } catch (error) {
        console.error('Error rendering emotes:', error, message);
        // Fallback to plain text
        contentElement.textContent = message.content;
    }
}

/**
 * Render a chat message
 * @param {Object} message - The chat message object
 * @param {HTMLElement} container - The container to render into
 */
function renderChatMessage(message, container) {
    try {
        // Create header with user info
        const header = document.createElement('div');
        header.className = 'event-header';

        // Create a dedicated container for badges
        const badgesContainer = document.createElement('div');
        badgesContainer.className = 'chat-badges';

        // Add badges if available
        if (message.author && message.author.badges) {
            addBadgesToElement(message.author.badges, message.author, badgesContainer);
            // Only append badges container if it has badges
            if (badgesContainer.childNodes.length > 0) {
                header.appendChild(badgesContainer);
            }
        }

        // Add username
        const username = document.createElement('span');
        username.className = 'username';
        if (message.author && message.author.color) {
            username.style.color = message.author.color;
        }
        username.textContent = message.author?.display_name || message.author?.name || 'Anonymous';
        header.appendChild(username);

        container.appendChild(header);

        // Add message content
        const content = document.createElement('div');
        content.className = 'event-content';

        // Use shared emote rendering function
        renderContentWithEmotes(content, message);

        container.appendChild(content);
    } catch (error) {
        console.error('Error rendering chat message:', error, message);
        // Create a fallback simple message if something goes wrong
        const fallbackMsg = document.createElement('div');
        fallbackMsg.className = 'event-content';
        fallbackMsg.textContent = message.content || '(message rendering error)';
        container.appendChild(fallbackMsg);
    }
}

/**
 * Render a command message
 * @param {Object} message - The command message object
 * @param {HTMLElement} container - The container to render into
 */
function renderCommandMessage(message, container) {
    // Create header with user info
    const header = document.createElement('div');
    header.className = 'event-header';

    // Add badges if available
    if (message.author && message.author.badges) {
        addBadgesToElement(message.author.badges, message.author, header);
    }

    // Add username
    const username = document.createElement('span');
    username.className = 'username';
    if (message.author && message.author.color) {
        username.style.color = message.author.color;
    }
    username.textContent = message.author?.display_name || message.author?.name || 'Anonymous';
    header.appendChild(username);

    // Add command indicator
    const indicator = document.createElement('span');
    indicator.className = 'command-indicator';
    indicator.textContent = 'COMMAND';
    header.appendChild(indicator);

    container.appendChild(header);

    // Add command content with emote support
    const content = document.createElement('div');
    content.className = 'event-content command-content';
    renderContentWithEmotes(content, message);
    container.appendChild(content);
}

/**
 * Render a subscription message
 * @param {Object} message - The subscription message object
 * @param {HTMLElement} container - The container to render into
 */
function renderSubscriptionMessage(message, container) {
    const content = document.createElement('div');
    content.className = 'event-content subscription-content';

    // Create formatted subscription text
    let subText = 'New subscription';
    if (message.event_data) {
        const data = message.event_data;
        if (data.is_gift) {
            subText = `${data.gifter_name || 'Someone'} gifted a sub to ${data.recipient_name || 'a viewer'}`;
        } else if (data.months > 1) {
            subText = `${message.author?.display_name || 'Someone'} resubscribed for ${data.months} months`;
        } else {
            subText = `${message.author?.display_name || 'Someone'} subscribed`;
        }

        // Override content for emote parsing if needed
        if (!message.content) {
            message.content = subText;
        }
    }

    // Use the shared emote rendering function
    renderContentWithEmotes(content, message);

    container.appendChild(content);
}

/**
 * Render a channel point redemption
 * @param {Object} message - The redeem message object
 * @param {HTMLElement} container - The container to render into
 */
function renderRedeemMessage(message, container) {
    const content = document.createElement('div');
    content.className = 'event-content redeem-content';

    // Create formatted redeem text
    let redeemText = 'Channel points redeemed';
    if (message.event_data) {
        const data = message.event_data;
        redeemText = `${message.author?.display_name || 'Someone'} redeemed "${data.reward_title || 'a reward'}" for ${data.reward_cost || '?'} points`;

        // Override content for emote parsing if needed
        if (!message.content) {
            message.content = redeemText;
        }
    }

    // Use the shared emote rendering function
    renderContentWithEmotes(content, message);

    container.appendChild(content);
}

/**
 * Render a raid message
 * @param {Object} message - The raid message object
 * @param {HTMLElement} container - The container to render into
 */
function renderRaidMessage(message, container) {
    const content = document.createElement('div');
    content.className = 'event-content raid-content';

    // Create formatted raid text
    let raidText = 'New raid';
    if (message.event_data) {
        const data = message.event_data;
        raidText = `${data.from_broadcaster_name || 'Someone'} raided with ${data.viewers || '?'} viewers`;

        // Override content for emote parsing if needed
        if (!message.content) {
            message.content = raidText;
        }
    }

    // Use the shared emote rendering function
    renderContentWithEmotes(content, message);

    container.appendChild(content);
}

/**
 * Render a system/admin message
 * @param {Object} message - The system message object
 * @param {HTMLElement} container - The container to render into
 */
function renderSystemMessage(message, container) {
    const content = document.createElement('div');
    content.className = 'event-content system-content';

    // Use the shared emote rendering function
    renderContentWithEmotes(content, message);

    container.appendChild(content);
}

/**
 * Render a generic message
 * @param {Object} message - The generic message object
 * @param {HTMLElement} container - The container to render into
 */
function renderGenericMessage(message, container) {
    const content = document.createElement('div');
    content.className = 'event-content';

    // If no content exists, create a default message
    if (!message.content) {
        message.content = `Event: ${message.type || 'unknown'}`;
    }

    // Use the shared emote rendering function
    renderContentWithEmotes(content, message);

    container.appendChild(content);
}
