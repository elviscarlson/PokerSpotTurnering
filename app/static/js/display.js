"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const app = document.querySelector("[data-display-app]");
    if (!app) return;
    const element = selector => app.querySelector(selector);
    const clock = element(".display-clock");
    const timer = element("[data-display-timer]");
    const status = element("[data-display-status]");
    const stage = element("[data-display-stage]");
    const progress = element("[data-level-progress]");
    const progressFill = element("[data-level-progress-fill]");
    const progressLabel = element("[data-level-progress-label]");
    const payouts = element("[data-display-payouts]");
    const announcement = element("[data-announcement]");
    const error = element("[data-display-error]");
    const fullscreenButton = element("[data-fullscreen]");
    const soundButton = element("[data-sound-toggle]");
    const numbers = new Intl.NumberFormat("sv-SE");
    const statusLabels = { READY: "REDO", RUNNING: "PÅGÅR", PAUSED: "PAUSAD", COMPLETED: "AVSLUTAD" };
    let state = null;
    let remaining = 0;
    let lastTickAt = performance.now();
    let announcementTimeout;
    let controlsTimeout;
    let soundEnabled = true;
    let audioContext;

    function formatTime(seconds) {
        const safe = Math.max(0, Math.floor(seconds));
        return `${String(Math.floor(safe / 60)).padStart(2, "0")}:${String(safe % 60).padStart(2, "0")}`;
    }

    function prepareAudio() {
        const AudioContext = window.AudioContext || window.webkitAudioContext;
        if (!soundEnabled || !AudioContext) return;
        if (!audioContext) audioContext = new AudioContext();
        if (audioContext.state === "suspended") audioContext.resume().catch(() => {});
    }

    function playTone(frequency, duration, delay = 0) {
        if (!soundEnabled || !audioContext || audioContext.state !== "running") return;
        const oscillator = audioContext.createOscillator();
        const gain = audioContext.createGain();
        const start = audioContext.currentTime + delay;
        oscillator.frequency.value = frequency;
        gain.gain.setValueAtTime(0.0001, start);
        gain.gain.exponentialRampToValueAtTime(0.18, start + 0.015);
        gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
        oscillator.connect(gain);
        gain.connect(audioContext.destination);
        oscillator.start(start);
        oscillator.stop(start + duration + 0.05);
        oscillator.onended = () => { oscillator.disconnect(); gain.disconnect(); };
    }

    function playLevelSound() {
        playTone(620, 0.14);
        playTone(820, 0.22, 0.17);
    }

    function playStartSound() {
        playTone(520, 0.12);
        playTone(660, 0.12, 0.13);
        playTone(880, 0.28, 0.26);
    }

    function showAnnouncement(eyebrow, title, copy, duration = 2600) {
        clearTimeout(announcementTimeout);
        element("[data-announcement-eyebrow]").textContent = eyebrow;
        element("[data-announcement-title]").textContent = title;
        element("[data-announcement-copy]").textContent = copy;
        announcement.hidden = false;
        announcementTimeout = setTimeout(() => { announcement.hidden = true; }, duration);
    }

    function detectAnnouncements(next) {
        if (!state) return;
        if (state.status !== "RUNNING" && next.status === "RUNNING") {
            playStartSound();
            showAnnouncement("TURNERING", "NU KÖR VI", `${numbers.format(next.current_level.small_blind)} / ${numbers.format(next.current_level.big_blind)}`, 2200);
        }
        if (next.current_level.position > state.current_level.position) {
            playLevelSound();
            showAnnouncement(`NIVÅ ${next.current_level.position}`, "NYA BLINDS", `${numbers.format(next.current_level.small_blind)} / ${numbers.format(next.current_level.big_blind)}`);
        }
        const paidPlaces = next.payouts.length;
        if (paidPlaces > 0 && state.players_remaining > paidPlaces + 1 && next.players_remaining === paidPlaces + 1) {
            showAnnouncement("TURNERING", "BUBBLAN", `${paidPlaces} prisplatser`, 3000);
        }
        if (paidPlaces > 0 && state.players_remaining > paidPlaces && next.players_remaining === paidPlaces) {
            playLevelSound();
            showAnnouncement("GRATTIS", "ALLA KVAR ÄR I PENGARNA", `${paidPlaces} prisplatser`, 3200);
        }
        if (state.status !== "COMPLETED" && next.status === "COMPLETED" && next.winner) {
            playStartSound();
            showAnnouncement("TURNERINGENS VINNARE", next.winner.name, `${numbers.format(next.winner.total_winnings)} kr i total vinst`, 6000);
        }
    }

    function renderPayouts() {
        const fragment = document.createDocumentFragment();
        for (const payout of state.payouts) {
            const card = document.createElement("div");
            card.className = "display-payout";
            const place = document.createElement("span");
            place.textContent = `${payout.place}:${payout.place === 1 || payout.place === 2 ? "a" : "e"}`;
            const amount = document.createElement("strong");
            amount.textContent = `${numbers.format(payout.amount)} kr`;
            card.append(place, amount);
            fragment.append(card);
        }
        if (!state.payouts.length) {
            const empty = document.createElement("span");
            empty.className = "display-payout-empty";
            empty.textContent = "Inga prisplatser";
            fragment.append(empty);
        }
        payouts.replaceChildren(fragment);
    }

    function updateStage() {
        let text = "";
        if (state.status === "COMPLETED" && state.winner) text = `Vinnare: ${state.winner.name}`;
        else if (state.status === "RUNNING" || state.status === "PAUSED") {
            const paid = state.payouts.length;
            if (paid > 0 && state.players_remaining === paid + 1) text = "Bubblan";
            else if (paid > 0 && state.players_remaining <= paid) text = "Alla kvar är i pengarna";
        }
        stage.textContent = text;
        stage.hidden = !text;
    }

    function renderClock() {
        if (!state) return;
        timer.textContent = state.status === "COMPLETED" ? "GG" : formatTime(remaining);
        const duration = Number(state.current_level.duration_seconds);
        const percent = state.status === "COMPLETED" || duration <= 0 ? 0 : Math.round(Math.min(1, Math.max(0, remaining / duration)) * 100);
        progressFill.style.width = `${percent}%`;
        progress.setAttribute("aria-valuenow", String(percent));
        progressLabel.textContent = `${percent} % kvar`;
        clock.dataset.urgency = state.status === "RUNNING" && remaining <= 60
            ? (remaining <= 15 ? "critical" : "warning") : "normal";
    }

    function renderState(next) {
        detectAnnouncements(next);
        state = next;
        remaining = Math.max(0, Number(state.remaining_seconds));
        lastTickAt = performance.now();
        element("[data-display-level]").textContent = state.current_level.position;
        element("[data-display-small]").textContent = numbers.format(state.current_level.small_blind);
        element("[data-display-big]").textContent = numbers.format(state.current_level.big_blind);
        element("[data-display-remaining]").textContent = state.players_remaining;
        element("[data-display-total]").textContent = state.players_total;
        element("[data-display-prize-pool]").textContent = numbers.format(state.prize_pool);
        element("[data-display-bounty-pool]").textContent = numbers.format(state.bounty_pool);
        element("[data-display-bounty-row]").hidden = !state.bounty_enabled;
        status.textContent = statusLabels[state.status] || state.status;
        status.dataset.status = state.status;
        element("[data-display-next]").textContent = state.next_level
            ? `${numbers.format(state.next_level.small_blind)} / ${numbers.format(state.next_level.big_blind)}`
            : "Sista nivån";
        renderPayouts();
        updateStage();
        renderClock();
        error.hidden = true;
    }

    async function syncState() {
        try {
            const response = await fetch(`/api/tournaments/${app.dataset.tournamentId}/state`, {
                headers: { Accept: "application/json" }, cache: "no-store",
            });
            if (!response.ok) throw new Error("Kunde inte hämta turneringen.");
            renderState(await response.json());
        } catch (failure) {
            error.hidden = false;
            console.error(failure);
        } finally {
            // Schedule after the response to avoid overlapping polls on a slow connection.
            setTimeout(syncState, 2000);
        }
    }

    function visualTick() {
        if (state && state.status === "RUNNING" && error.hidden) {
            const elapsed = Math.floor((performance.now() - lastTickAt) / 1000);
            if (elapsed >= 1) {
                remaining = Math.max(0, remaining - elapsed);
                lastTickAt += elapsed * 1000;
                renderClock();
            }
        }
        requestAnimationFrame(visualTick);
    }

    function showControls() {
        document.body.classList.remove("cursor-hidden", "controls-hidden");
        clearTimeout(controlsTimeout);
        controlsTimeout = setTimeout(() => {
            document.body.classList.add("controls-hidden");
            if (document.fullscreenElement) document.body.classList.add("cursor-hidden");
        }, 3500);
    }

    fullscreenButton.addEventListener("click", async event => {
        if (event.detail > 0) fullscreenButton.blur();
        try {
            if (document.fullscreenElement) await document.exitFullscreen();
            else await document.documentElement.requestFullscreen();
        } catch (failure) { console.error(failure); }
    });
    document.addEventListener("fullscreenchange", () => {
        fullscreenButton.textContent = document.fullscreenElement ? "Lämna helskärm" : "Helskärm";
        showControls();
    });
    soundButton.addEventListener("click", event => {
        if (event.detail > 0) soundButton.blur();
        soundEnabled = !soundEnabled;
        soundButton.textContent = soundEnabled ? "Ljud på" : "Ljud av";
        soundButton.setAttribute("aria-pressed", String(soundEnabled));
        if (soundEnabled) prepareAudio();
    });
    document.addEventListener("pointerdown", prepareAudio);
    document.addEventListener("pointermove", showControls);
    document.addEventListener("keydown", showControls);
    document.addEventListener("focusin", showControls);
    showControls();
    syncState();
    requestAnimationFrame(visualTick);
});
