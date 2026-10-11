"use strict";

// A short sword swish followed by several ringing metal overtones.
// Create audio only inside the user's button click (mobile autoplay rules).
let katanaAudio;
async function playKatanaSound() {
    const AudioContext = window.AudioContext || window.webkitAudioContext;
    if (!AudioContext) return;
    if (!katanaAudio || katanaAudio.state === "closed") katanaAudio = new AudioContext();
    if (katanaAudio.state === "suspended") await katanaAudio.resume();
    const context = katanaAudio;
    const start = context.currentTime;
    const output = context.createGain();
    output.gain.value = .22;
    output.connect(context.destination);

    const noise = context.createBuffer(1, Math.ceil(context.sampleRate * .28), context.sampleRate);
    const samples = noise.getChannelData(0);
    for (let i = 0; i < samples.length; i++) samples[i] = Math.random() * 2 - 1;
    const swish = context.createBufferSource();
    swish.buffer = noise;
    const filter = context.createBiquadFilter();
    filter.type = "bandpass";
    filter.Q.value = .7;
    filter.frequency.setValueAtTime(650, start);
    filter.frequency.exponentialRampToValueAtTime(6000, start + .13);
    filter.frequency.exponentialRampToValueAtTime(1200, start + .28);
    const envelope = context.createGain();
    envelope.gain.setValueAtTime(.001, start);
    envelope.gain.exponentialRampToValueAtTime(.8, start + .07);
    envelope.gain.exponentialRampToValueAtTime(.001, start + .28);
    swish.connect(filter).connect(envelope).connect(output);
    swish.start(start);
    swish.onended = () => { swish.disconnect(); filter.disconnect(); envelope.disconnect(); };

    [1470, 2390, 3540, 4910].forEach((frequency, index) => {
        const ring = context.createOscillator();
        ring.type = "sine";
        ring.frequency.setValueAtTime(frequency, start + .14);
        ring.frequency.exponentialRampToValueAtTime(frequency * .96, start + .7);
        const gain = context.createGain();
        gain.gain.setValueAtTime(.001, start);
        gain.gain.setValueAtTime(.26 / (index + 1), start + .14);
        gain.gain.exponentialRampToValueAtTime(.001, start + .85);
        ring.connect(gain).connect(output);
        ring.start(start + .14);
        ring.stop(start + .86);
        ring.onended = () => {
            ring.disconnect(); gain.disconnect();
            if (index === 3) output.disconnect();
        };
    });
}

document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-leo-page]");
    if (!page) return;
    const button = page.querySelector("[data-leo-strike]");
    const response = page.querySelector("[data-leo-response]");
    const soundToggle = page.querySelector("[data-leo-sound]");
    let soundEnabled = true;
    soundToggle.addEventListener("click", () => {
        soundEnabled = !soundEnabled;
        soundToggle.setAttribute("aria-pressed", String(soundEnabled));
        soundToggle.textContent = soundEnabled ? "Ljud på" : "Ljud av";
    });
    const lines = [
        "Alla andra checkar respektfullt.",
        "Svärdet är vasst. Pokerfejset är vassare.",
        "Leo synar. Bordet svettas.",
        "Marker? Leo spelar med legendstatus.",
    ];
    let turn = 0;
    button.addEventListener("click", () => {
        if (soundEnabled) void playKatanaSound().catch(() => {});
        button.disabled = true;
        response.textContent = lines[turn++ % lines.length];
        page.classList.add("leo-striking");
        setTimeout(() => {
            page.classList.remove("leo-striking");
            button.disabled = false;
        }, 750);
    });
});
