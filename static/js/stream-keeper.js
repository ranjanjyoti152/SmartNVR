/**
 * Stream-Keeper - Ensures video streams remain active when the browser tab is minimized
 * For SmartNVR surveillance system
 */

class StreamKeeper {
    constructor(options = {}) {
        this.options = {
            pingInterval: options.pingInterval || 10000, // Ping interval in ms (10 seconds default)
            debug: options.debug || false,
            audioFeedback: options.audioFeedback || false
        };
        
        this.isHidden = false;
        this.streams = new Map(); // Map to store stream elements and their original sources
        this.worker = null;
        this.audioContext = null;
        this.audioElement = null;
        
        // Initialize the Stream Keeper
        this.init();
    }
    
    init() {
        // Get the visibility API properties based on browser
        this.visibilityProps = this.getVisibilityProps();
        if (!this.visibilityProps) {
            this.log("Browser doesn't support Page Visibility API, using fallback method");
            // Fallback to blur/focus events
            window.addEventListener('blur', () => this.handleVisibilityChange(true));
            window.addEventListener('focus', () => this.handleVisibilityChange(false));
        } else {
            // Listen for visibility change events
            document.addEventListener(this.visibilityProps.visibilityChange, 
                () => this.handleVisibilityChange(document[this.visibilityProps.hidden]), 
                false
            );
            
            // Set initial state
            this.isHidden = document[this.visibilityProps.hidden];
        }
        
        // Create a background worker for keeping the tab active
        this.createWorker();
        
        // Initialize audio context for keeping tab active if needed
        if (this.options.audioFeedback) {
            this.initAudio();
        }
        
        this.log("Stream-Keeper initialized");
    }
    
    getVisibilityProps() {
        // Different browsers have different visibility properties
        let hidden, visibilityChange;
        
        if (typeof document.hidden !== "undefined") {
            hidden = "hidden";
            visibilityChange = "visibilitychange";
        } else if (typeof document.msHidden !== "undefined") {
            hidden = "msHidden";
            visibilityChange = "msvisibilitychange";
        } else if (typeof document.webkitHidden !== "undefined") {
            hidden = "webkitHidden";
            visibilityChange = "webkitvisibilitychange";
        } else {
            return null; // Not supported
        }
        
        return { hidden, visibilityChange };
    }
    
    handleVisibilityChange(isHidden) {
        this.isHidden = isHidden;
        this.log(`Page visibility changed: ${isHidden ? 'hidden' : 'visible'}`);
        
        if (isHidden) {
            this.activateKeepAlive();
        } else {
            this.deactivateKeepAlive();
        }
    }
    
    registerStream(streamElement) {
        if (!streamElement || !(streamElement instanceof HTMLImageElement)) {
            this.log("Invalid stream element provided", true);
            return false;
        }
        
        const streamId = streamElement.id || `stream-${Math.random().toString(36).substr(2, 9)}`;
        if (!streamElement.id) {
            streamElement.id = streamId;
        }
        
        this.streams.set(streamId, {
            element: streamElement,
            originalSrc: streamElement.src
        });
        
        this.log(`Registered stream: ${streamId}`);
        return streamId;
    }
    
    registerAllStreamsBySelector(selector = 'img[src*="video_feed"]') {
        const streamElements = document.querySelectorAll(selector);
        this.log(`Found ${streamElements.length} streams to register`);
        
        streamElements.forEach(element => {
            this.registerStream(element);
        });
    }
    
    activateKeepAlive() {
        this.log("Activating keep-alive mechanisms for streams");
        
        // Start the worker to ping the page
        if (this.worker) {
            this.worker.postMessage({ action: 'start', interval: this.options.pingInterval });
        }
        
        // Play silent audio to prevent some browsers from throttling
        if (this.options.audioFeedback && this.audioContext && this.audioElement) {
            this.playKeepAliveAudio();
        }
        
        // Force refresh streams periodically
        this.startStreamRefresher();
    }
    
    deactivateKeepAlive() {
        this.log("Deactivating keep-alive mechanisms");
        
        // Stop the worker
        if (this.worker) {
            this.worker.postMessage({ action: 'stop' });
        }
        
        // Stop audio
        if (this.audioElement) {
            this.audioElement.pause();
            this.audioElement.currentTime = 0;
        }
        
        // Stop stream refresher
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }
    
    createWorker() {
        // Create a blob with the worker code
        const workerCode = `
            let pingInterval = null;
            
            self.onmessage = function(e) {
                const data = e.data;
                
                if (data.action === 'start') {
                    // Clear any existing interval
                    if (pingInterval) {
                        clearInterval(pingInterval);
                    }
                    
                    // Start a new ping interval
                    pingInterval = setInterval(() => {
                        self.postMessage({ action: 'ping', time: Date.now() });
                    }, data.interval || 10000);
                    
                    self.postMessage({ action: 'started' });
                } else if (data.action === 'stop') {
                    if (pingInterval) {
                        clearInterval(pingInterval);
                        pingInterval = null;
                    }
                    self.postMessage({ action: 'stopped' });
                }
            };
        `;
        
        try {
            const blob = new Blob([workerCode], { type: 'application/javascript' });
            const workerUrl = URL.createObjectURL(blob);
            
            this.worker = new Worker(workerUrl);
            
            this.worker.onmessage = (e) => {
                const data = e.data;
                if (data.action === 'ping') {
                    this.handleWorkerPing(data.time);
                } else {
                    this.log(`Worker status: ${data.action}`);
                }
            };
            
            this.worker.onerror = (error) => {
                this.log(`Worker error: ${error.message}`, true);
            };
        } catch (error) {
            this.log(`Failed to create worker: ${error.message}`, true);
        }
    }
    
    handleWorkerPing(timestamp) {
        // This function is called every ping interval when the tab is hidden
        this.log(`Worker ping: ${new Date(timestamp).toISOString()}`);
        
        // Trigger a "tick" event for other components to listen to
        const event = new CustomEvent('streamkeeper:tick', { 
            detail: { 
                timestamp,
                isHidden: this.isHidden
            }
        });
        document.dispatchEvent(event);
    }
    
    initAudio() {
        try {
            // Create a silent audio element
            this.audioElement = document.createElement('audio');
            this.audioElement.loop = true;
            this.audioElement.volume = 0.01; // Very quiet
            
            // Create a very short silent audio file using data URI
            // 1 second of silence
            this.audioElement.src = 'data:audio/mp3;base64,SUQzBAAAAAABEVRYWFgAAAAtAAADY29tbWVudABCaWdTb3VuZEJhbmsuY29tIC8gTGFTb25vdGhlcXVlLm9yZwBURU5DAAAAHQAAA1N3aXRjaCBQbHVzIMKpIE5DSCBTb2Z0d2FyZQBUSVQyAAAABgAAAzIyMzUAVFNTRQAAAA8AAANMYXZmNTcuODMuMTAwAAAAAAAAAAAAAAD/80DEAAAAA0gAAAAATEFNRTMuMTAwVVVVVVVVVVVVVUxBTUUzLjEwMFVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQsRbAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVf/zQMSkAAADSAAAAABVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVVV';
            
            document.body.appendChild(this.audioElement);
            
            this.log("Audio keep-alive initialized");
        } catch (error) {
            this.log(`Failed to initialize audio: ${error.message}`, true);
        }
    }
    
    playKeepAliveAudio() {
        if (this.audioElement) {
            // Try to play the silent audio
            this.audioElement.play().catch(error => {
                this.log(`Failed to play audio: ${error.message}`, true);
            });
        }
    }
    
    startStreamRefresher() {
        // Clear any existing interval
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
        
        // Set up the stream refresher
        this.refreshInterval = setInterval(() => {
            this.refreshAllStreams();
        }, this.options.pingInterval);
    }
    
    refreshAllStreams() {
        this.log("Refreshing all streams");
        
        this.streams.forEach((streamInfo, streamId) => {
            try {
                const element = streamInfo.element;
                if (element && element.parentNode) {
                    // Add a timestamp to force refresh without browser caching
                    const src = streamInfo.originalSrc;
                    const separator = src.includes('?') ? '&' : '?';
                    element.src = `${src}${separator}_t=${Date.now()}`;
                    
                    this.log(`Refreshed stream: ${streamId}`);
                }
            } catch (error) {
                this.log(`Error refreshing stream ${streamId}: ${error.message}`, true);
            }
        });
    }
    
    log(message, isError = false) {
        if (this.options.debug || isError) {
            const prefix = isError ? 'ERROR' : 'INFO';
            console.log(`[StreamKeeper ${prefix}] ${message}`);
        }
    }
}

// Initialize StreamKeeper when the document is loaded
document.addEventListener('DOMContentLoaded', () => {
    window.streamKeeper = new StreamKeeper({
        pingInterval: 5000, // Check every 5 seconds
        debug: true,
        audioFeedback: true // Use silent audio to keep the tab active
    });
    
    // Register all video feed streams
    window.streamKeeper.registerAllStreamsBySelector('img[src*="video_feed"]');
});