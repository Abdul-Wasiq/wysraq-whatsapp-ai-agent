# 001: The Zombie Chrome Killer (Graceful Shutdowns)

**Date:** April 2026
**Status:** Solved

### The Problem
During local testing, restarting the Node.js server (using `Ctrl+C`) would crash the application on the next boot with the error: `The browser is already running... Access Denied`.

Because `whatsapp-web.js` uses Puppeteer under the hood, killing the Node.js terminal instantly killed the backend, but left the invisible headless Chromium browsers running in the background RAM. These "zombie" browsers kept a permanent lock on the `.wwebjs_auth` session folders. When the server rebooted and tried to read the folder, it was blocked.

### The Solution
Instead of forcing users to open Task Manager and manually kill Chrome processes, I implemented a graceful shutdown interceptor. 

I added a `SIGINT` listener to the Node.js process. When a termination signal is received, the server pauses, loops through the active `sessions` dictionary, and runs `client.destroy()` on every active WhatsApp client before finally executing `process.exit(0)`.

```javascript
process.on('SIGINT', async () => {
    console.log('Shutting down DevX Switchboard cleanly...');
    for (const userId in sessions) {
        if (sessions[userId].client) {
            await sessions[userId].client.destroy(); 
        }
    }
    process.exit(0);
});
