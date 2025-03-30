/**
 * Configuration for the Twitch chat application
 * Contains all user-adjustable settings
 */
export const config = {
    fadeOutDelay: 15000,      // Message fade out time in ms (0 to disable)
    maxMessages: 100,         // Maximum messages to keep in DOM for scrolling
    emoteSize: 1.5,           // Emote size multiplier
    badgeSize: 1.2,           // Badge size multiplier
    messageLimit: 200,        // Character limit for messages
    hideBotMessages: true,    // Hide known bot messages
    botUsernames: ['nightbot', 'streamelements', 'streamlabs'],
    animateMessages: true,    // Enable message animations
    useColoredNames: true,    // Use Twitch colors for usernames
    showTimestamps: false,    // Show message timestamps
    enableNicknames: true,    // Enable custom nicknames
    enableBTTV: true,         // Enable BTTV emotes
    enable7TV: true,          // Enable 7TV emotes
    debug: true,              // Enable debug logging
    shouldAutoScroll: true,
    wasAtBottom: true,
    resizeTimer: null,
    initialWidth: window.innerWidth,
    hasMoreHistory: true,
    lastLoadedIndex : 0, // Start with no messages loaded yet
    messagesPerLoad : 50, // How many messages to load each time
    channelName: 'beastyrabbit',
    isTwitchChatActive: false,
    twitchChatLoaded: false,
};

export const filterMap = {
    'chat': ['chat'],
    'command': ['commands'],
    'redeem': ['redeem'],
    'subscription': ['subscription', 'sub'],
    'raid': ['raid'],
    'system': ['system', 'admin'],
    'helper': ['helper']
};

