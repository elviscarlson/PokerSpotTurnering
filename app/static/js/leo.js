"use strict";

// Layer a fast blade sweep, a bass impact and ringing metal overtones.
// Create audio only inside the user's button click (mobile autoplay rules).
let katanaAudio;
let katanaOutput;
async function playKatanaSound() {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    if (!katanaAudio || katanaAudio.state === "closed") katanaAudio = new AudioContext();
    if (katanaAudio.state === "suspended") await katanaAudio.resume();
    const context = katanaAudio;
    const start = context.currentTime;
    const output = context.createGain();
    katanaOutput = output;
    output.gain.value = .58;
    const compressor = context.createDynamicsCompressor();
    compressor.threshold.value = -14;
    compressor.knee.value = 12;
    compressor.ratio.value = 8;
    compressor.attack.value = .003;
    compressor.release.value = .15;
    output.connect(compressor).connect(context.destination);
    let activeSources = 0;
    const cleanUpWhenEnded = (source, ...nodes) => {
        activeSources++;
        source.onended = () => {
            source.disconnect();
            nodes.forEach(node => node.disconnect());
            if (--activeSources === 0) { output.disconnect(); compressor.disconnect(); }
        };
    };

    const noise = context.createBuffer(1, Math.ceil(context.sampleRate * .38), context.sampleRate);
    const samples = noise.getChannelData(0);
    for (let i = 0; i < samples.length; i++) samples[i] = Math.random() * 2 - 1;
    const swish = context.createBufferSource();
    swish.buffer = noise;
    const filter = context.createBiquadFilter();
    filter.type = "bandpass";
    filter.Q.value = .55;
    filter.frequency.setValueAtTime(400, start);
    filter.frequency.exponentialRampToValueAtTime(7500, start + .14);
    filter.frequency.exponentialRampToValueAtTime(900, start + .38);
    const envelope = context.createGain();
    envelope.gain.setValueAtTime(.001, start);
    envelope.gain.exponentialRampToValueAtTime(1.2, start + .1);
    envelope.gain.exponentialRampToValueAtTime(.001, start + .38);
    swish.connect(filter).connect(envelope).connect(output);
    cleanUpWhenEnded(swish, filter, envelope);
    swish.start(start);

    const impact = context.createOscillator();
    impact.type = "sine";
    impact.frequency.setValueAtTime(150, start + .14);
    impact.frequency.exponentialRampToValueAtTime(38, start + .65);
    const bass = context.createGain();
    bass.gain.setValueAtTime(.001, start);
    bass.gain.exponentialRampToValueAtTime(1, start + .16);
    bass.gain.exponentialRampToValueAtTime(.001, start + .7);
    impact.connect(bass).connect(output);
    cleanUpWhenEnded(impact, bass);
    impact.start(start + .14);
    impact.stop(start + .72);

    [790, 1470, 2390, 3540, 4910].forEach((frequency, index) => {
        const ring = context.createOscillator();
        ring.type = "sine";
        ring.frequency.setValueAtTime(frequency, start + .14);
        ring.frequency.exponentialRampToValueAtTime(frequency * .93, start + .9);
        const gain = context.createGain();
        gain.gain.setValueAtTime(.001, start);
        gain.gain.setValueAtTime(.35 / (index + 1), start + .14);
        gain.gain.exponentialRampToValueAtTime(.001, start + 1.05);
        ring.connect(gain).connect(output);
        cleanUpWhenEnded(ring, gain);
        ring.start(start + .14);
        ring.stop(start + 1.06);
    });
}

document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-leo-page]");
    if (!page) return;
    const button = page.querySelector("[data-leo-strike]");
    const response = page.querySelector("[data-leo-response]");
    const soundToggle = page.querySelector("[data-leo-sound]");
    const quotes = Array.from(page.querySelectorAll("[data-leo-quote]"));
    const sourceLink = page.querySelector("[data-leo-quote-source]");
    let currentQuote = null;
    const stopQuotes = () => {
        currentQuote = null;
        quotes.forEach(audio => { audio.pause(); audio.currentTime = 0; });
    };
    let soundEnabled = true;
    soundToggle.addEventListener("click", () => {
        soundEnabled = !soundEnabled;
        soundToggle.setAttribute("aria-pressed", String(soundEnabled));
        soundToggle.textContent = soundEnabled ? "Ljud på" : "Ljud av";
        if (!soundEnabled) {
            stopQuotes();
            if (katanaAudio && katanaOutput) katanaOutput.gain.setTargetAtTime(0, katanaAudio.currentTime, .015);
        }
    });
    let turn = 0;
    button.addEventListener("click", () => {
        stopQuotes();
        const quote = quotes[turn++ % quotes.length];
        const line = quote ? quote.dataset.quote : "Bordet är ditt.";
        response.textContent = quote ? `“${line}” — LeBron James` : line;
        if (quote && sourceLink) {
            sourceLink.href = quote.dataset.source;
            sourceLink.hidden = false;
            sourceLink.parentElement.hidden = false;
        }
        if (soundEnabled) {
            void playKatanaSound().catch(() => {});
            if (quote) {
                currentQuote = quote;
                quote.volume = .9;
                // Play a local recording directly in the click, including on mobile.
                // Stop the previous clip before starting another; never synthesize speech.
                void quote.play().catch(error => {
                    if (currentQuote === quote && soundEnabled && error.name !== "AbortError") {
                        response.textContent += " (Ljudklippet kunde inte spelas.)";
                    }
                });
            }
        }
        button.disabled = true;
        page.classList.add("leo-striking");
        setTimeout(() => {
            page.classList.remove("leo-striking");
            button.disabled = false;
        }, 750);
    });
    window.addEventListener("pagehide", stopQuotes);
});
