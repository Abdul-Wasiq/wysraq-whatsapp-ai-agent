const { Client, LocalAuth } = require('whatsapp-web.js');
const qrcode = require('qrcode-terminal');
const axios = require('axios');
const http = require('http');
const fs = require('fs');
const path = require('path');

const AUTH_PATH = path.join(__dirname, '.wwebjs_auth');

// 🚀 THE ZOMBIE KILLER: Safely shut down all browsers if you Ctrl+C the terminal
process.on('SIGINT', async () => {
    console.log('\n🛑 Shutting down DevX Switchboard cleanly...');
    
    // Loop through every active session and destroy the browser
    for (const userId in sessions) {
        const session = sessions[userId];
        if (session.client) {
            console.log(`Killing browser for User ${userId}...`);
            try { 
                await session.client.destroy(); 
            } catch (e) {
                console.log(`Could not kill browser for ${userId}:`, e.message);
            }
        }
    }
    
    console.log('✅ All browsers safely closed. Goodbye!');
    process.exit(0);
});


const sessions = {}; 

function getSession(userId) {
    if (!sessions[userId]) {
        sessions[userId] = {
            client: null,
            qr: null,
            isConnected: false,
            isStarting: false
        };
    }
    return sessions[userId];
}

function bindClientEvents(activeClient, userId) {
    const session = getSession(userId);

    activeClient.on('qr', (qr) => {
        console.log(`[User ${userId}] QR Code scan karo:`);
        qrcode.generate(qr, { small: true });
        session.qr = qr;
        session.isConnected = false;
    });

    activeClient.on('ready', () => {
        console.log(`[User ${userId}] Bot ready hai!`);
        session.isConnected = true;
        session.qr = null;
    });

    activeClient.on('disconnected', (reason) => {
        console.log(`[User ${userId}] Disconnected:`, reason);
        session.isConnected = false;
        session.qr = null;
    });

    activeClient.on('message', async (msg) => {
        console.log(`[User ${userId}] Message aaya:`, msg.body);

        try {
            // 🚀 DYNAMIC ID: Node.js knows exactly whose bot this is!
            const response = await axios.post('http://localhost:8000/chat', {
                user_id: parseInt(userId), 
                phone: msg.from,
                message: msg.body
            });

            const status = response.data.status;
            const reply = response.data.reply;

            if (status === 'answered' && reply) {
                await msg.reply(reply);
            } else {
                console.log(`[User ${userId}] Message ignored by AI classifier.`);
            }

        } catch (error) {
            console.log(`[User ${userId}] FastAPI error:`, error.message);
        }
    });
}

function findChrome() {
    const candidates = [
        'C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe',
        'C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe',
        (process.env.LOCALAPPDATA || '') + '\\Google\\Chrome\\Application\\chrome.exe',
        '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome',
        '/usr/bin/google-chrome',
        '/usr/bin/chromium-browser',
    ];
    for (const p of candidates) {
        try { if (fs.existsSync(p)) return p; } catch (_) {}
    }
    return null; 
}

async function startClient(userId) {
    const session = getSession(userId);
    if (session.isStarting || session.client) return;
    
    session.isStarting = true;

    try {
        const chromePath = findChrome();
        const puppeteerConfig = {
            headless: true,
            protocolTimeout: 120000,
            args: ['--no-sandbox', '--disable-setuid-sandbox', '--disable-dev-shm-usage', '--disable-gpu']
        };
        if (chromePath) puppeteerConfig.executablePath = chromePath;

        // 🚀 ISOLATION: Each user gets their own specific auth folder!
        const newClient = new Client({
            authStrategy: new LocalAuth({ 
                dataPath: AUTH_PATH,
                clientId: `user_${userId}` 
            }),
            puppeteer: puppeteerConfig
        });

        bindClientEvents(newClient, userId);
        session.client = newClient;
        await session.client.initialize();
    } catch (error) {
        console.log(`[User ${userId}] Init error:`, error.message);
        session.client = null;
        session.isConnected = false;
        session.qr = null;
    } finally {
        session.isStarting = false;
    }
}

// 🚀 UPGRADED HTTP SERVER: Now expects a userId in the URL!
const server = http.createServer((req, res) => {
    res.setHeader('Access-Control-Allow-Origin', '*');
    res.setHeader('Access-Control-Allow-Methods', 'GET,POST,OPTIONS');
    res.setHeader('Access-Control-Allow-Headers', 'Content-Type');
    res.setHeader('Content-Type', 'application/json');

    if (req.method === 'OPTIONS') {
        res.statusCode = 204;
        return res.end();
    }

    // Extract user_id from the URL (e.g., /qr?userId=42)
    const url = new URL(req.url, `http://${req.headers.host}`);
    const userId = url.searchParams.get('userId');

    if (!userId) {
        res.statusCode = 400;
        return res.end(JSON.stringify({ error: "Missing userId parameter" }));
    }

    const session = getSession(userId);

    if (url.pathname === '/qr' && req.method === 'GET') {
        // If the bot isn't running yet, start it!
        if (!session.client && !session.isStarting) {
            startClient(userId);
        }

        if (session.qr) {
            res.end(JSON.stringify({ qr: session.qr }));
        } else if (session.isConnected) {
            res.end(JSON.stringify({ connected: true }));
        } else {
            res.end(JSON.stringify({ qr: null }));
        }
    }
    
    else if (url.pathname === '/disconnect' && req.method === 'POST') {
        if (session.client) {
            session.client.logout().catch(() => {});
            session.client.destroy().catch(() => {});
            session.client = null;
        }
        session.isConnected = false;
        session.qr = null;
        
        try {
            const userAuthPath = path.join(AUTH_PATH, `session-user_${userId}`);
            fs.rmSync(userAuthPath, { recursive: true, force: true });
        } catch(e) {}

        res.end(JSON.stringify({ success: true }));
    }
    else {
        res.end(JSON.stringify({ ok: true }));
    }
});

server.listen(3000, () => {
    console.log('🚀 DevX Switchboard running on http://localhost:3000');
});