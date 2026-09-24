"use strict";


document.addEventListener(
    "DOMContentLoaded",
    () => {
        const app =
            document.querySelector(
                "[data-display-app]"
            );

        if (!app) {
            return;
        }


        const tournamentId =
            app.dataset.tournamentId;

        const timerElement =
            app.querySelector(
                "[data-display-timer]"
            );

        const levelElement =
            app.querySelector(
                "[data-display-level]"
            );

        const smallElement =
            app.querySelector(
                "[data-display-small]"
            );

        const bigElement =
            app.querySelector(
                "[data-display-big]"
            );

        const nextElement =
            app.querySelector(
                "[data-display-next]"
            );

        const remainingElement =
            app.querySelector(
                "[data-display-remaining]"
            );

        const statusElement =
            app.querySelector(
                "[data-display-status]"
            );

        const payoutContainer =
            app.querySelector(
                "[data-display-payouts]"
            );

        const progressTitle =
            app.querySelector(
                "[data-display-progress-title]"
            );

        const progressCopy =
            app.querySelector(
                "[data-display-progress-copy]"
            );

        const fullscreenButton =
            app.querySelector(
                "[data-fullscreen]"
            );

        const soundButton =
            app.querySelector(
                "[data-sound-toggle]"
            );

        const announcement =
            app.querySelector(
                "[data-announcement]"
            );

        const announcementEyebrow =
            app.querySelector(
                "[data-announcement-eyebrow]"
            );

        const announcementTitle =
            app.querySelector(
                "[data-announcement-title]"
            );

        const announcementCopy =
            app.querySelector(
                "[data-announcement-copy]"
            );

        const errorElement =
            app.querySelector(
                "[data-display-error]"
            );


        let state = null;
        let localRemaining = 0;

        let lastTickAt =
            performance.now();

        let previousLevel = null;
        let previousStatus = null;
        let previousPlayersRemaining =
            null;

        let soundEnabled = true;
        let initialized = false;

        let announcementTimeout = null;
        let cursorTimeout = null;


        function formatTime(
            seconds
        ) {
            const safe =
                Math.max(
                    0,
                    Math.floor(seconds)
                );

            const minutes =
                Math.floor(
                    safe / 60
                );

            const remainder =
                safe % 60;

            return (
                String(minutes)
                    .padStart(2, "0")
                +
                ":"
                +
                String(remainder)
                    .padStart(2, "0")
            );
        }


        function playTone(
            frequency,
            duration,
            delay = 0
        ) {
            if (!soundEnabled) {
                return;
            }

            const AudioContext =
                window.AudioContext
                ||
                window.webkitAudioContext;

            if (!AudioContext) {
                return;
            }

            const context =
                new AudioContext();

            const oscillator =
                context.createOscillator();

            const gain =
                context.createGain();

            oscillator.type =
                "sine";

            oscillator.frequency.value =
                frequency;

            gain.gain.setValueAtTime(
                0.0001,
                context.currentTime
            );

            gain.gain.exponentialRampToValueAtTime(
                0.18,
                context.currentTime
                + delay
                + 0.015
            );

            gain.gain.exponentialRampToValueAtTime(
                0.0001,
                context.currentTime
                + delay
                + duration
            );

            oscillator.connect(
                gain
            );

            gain.connect(
                context.destination
            );

            oscillator.start(
                context.currentTime
                + delay
            );

            oscillator.stop(
                context.currentTime
                + delay
                + duration
                + 0.05
            );
        }


        function playLevelSound() {
            playTone(
                620,
                0.14
            );

            playTone(
                820,
                0.22,
                0.17
            );
        }


        function playStartSound() {
            playTone(
                520,
                0.12
            );

            playTone(
                660,
                0.12,
                0.13
            );

            playTone(
                880,
                0.28,
                0.26
            );
        }


        function showAnnouncement(
            {
                eyebrow,
                title,
                copy,
                duration = 2600,
            }
        ) {
            if (
                announcementTimeout
            ) {
                clearTimeout(
                    announcementTimeout
                );
            }

            announcementEyebrow.textContent =
                eyebrow;

            announcementTitle.textContent =
                title;

            announcementCopy.textContent =
                copy;

            announcement.hidden =
                false;

            announcementTimeout =
                setTimeout(
                    () => {
                        announcement.hidden =
                            true;
                    },
                    duration
                );
        }


        function renderPayouts() {
            payoutContainer.innerHTML =
                state.payouts
                    .map(
                        payout => `
                            <div class="display-payout">
                                <span>
                                    ${payout.place}
                                </span>

                                <strong>
                                    ${payout.amount}
                                    KR
                                </strong>
                            </div>
                        `
                    )
                    .join("");
        }


        function updateProgress() {
            if (
                state.status === "COMPLETED"
                &&
                state.winner
            ) {
                progressTitle.textContent =
                    "WINNER";

                progressCopy.textContent =
                    state.winner.name;

                return;
            }


            const paidPlaces =
                state.payouts.length;

            if (
                state.players_remaining
                === paidPlaces + 1
            ) {
                progressTitle.textContent =
                    "BUBBLE";

                progressCopy.textContent =
                    `${paidPlaces} paid`;

                return;
            }


            if (
                state.players_remaining
                <= paidPlaces
            ) {
                progressTitle.textContent =
                    "IN THE MONEY";

                progressCopy.textContent =
                    (
                        `${state.players_remaining}`
                        +
                        " players left"
                    );

                return;
            }


            progressTitle.textContent =
                "IN PLAY";

            progressCopy.textContent =
                (
                    `${state.players_remaining}`
                    +
                    " players remaining"
                );
        }


        function detectAnnouncements(
            newState
        ) {
            if (!initialized) {
                previousLevel =
                    newState.current_level.position;

                previousStatus =
                    newState.status;

                previousPlayersRemaining =
                    newState.players_remaining;

                initialized = true;

                return;
            }


            if (
                previousStatus !== "RUNNING"
                &&
                newState.status === "RUNNING"
            ) {
                playStartSound();

                showAnnouncement(
                    {
                        eyebrow:
                            "TOURNAMENT",
                        title:
                            "LET'S PLAY",
                        copy:
                            (
                                `${newState.current_level.small_blind}`
                                +
                                " / "
                                +
                                `${newState.current_level.big_blind}`
                            ),
                        duration:
                            2200,
                    }
                );
            }


            if (
                previousLevel !== null
                &&
                newState.current_level.position
                > previousLevel
            ) {
                playLevelSound();

                showAnnouncement(
                    {
                        eyebrow:
                            (
                                `LEVEL `
                                +
                                `${newState.current_level.position}`
                            ),
                        title:
                            "LEVEL UP",
                        copy:
                            (
                                `${newState.current_level.small_blind}`
                                +
                                " / "
                                +
                                `${newState.current_level.big_blind}`
                            ),
                        duration:
                            2600,
                    }
                );
            }


            const paidPlaces =
                newState.payouts.length;


            if (
                previousPlayersRemaining
                !== null
                &&
                previousPlayersRemaining
                > paidPlaces + 1
                &&
                newState.players_remaining
                === paidPlaces + 1
            ) {
                showAnnouncement(
                    {
                        eyebrow:
                            "TOURNAMENT",
                        title:
                            "BUBBLE",
                        copy:
                            `${paidPlaces} places paid`,
                        duration:
                            3000,
                    }
                );
            }


            if (
                previousPlayersRemaining
                !== null
                &&
                previousPlayersRemaining
                > paidPlaces
                &&
                newState.players_remaining
                === paidPlaces
            ) {
                playLevelSound();

                showAnnouncement(
                    {
                        eyebrow:
                            "CONGRATULATIONS",
                        title:
                            "IN THE MONEY",
                        copy:
                            `${paidPlaces} players paid`,
                        duration:
                            3200,
                    }
                );
            }


            if (
                previousStatus !== "COMPLETED"
                &&
                newState.status === "COMPLETED"
                &&
                newState.winner
            ) {
                playStartSound();

                showAnnouncement(
                    {
                        eyebrow:
                            "TOURNAMENT WINNER",
                        title:
                            newState.winner.name,
                        copy:
                            (
                                `${newState.winner.total_winnings}`
                                +
                                " KR total winnings"
                            ),
                        duration:
                            6000,
                    }
                );
            }


            previousLevel =
                newState.current_level.position;

            previousStatus =
                newState.status;

            previousPlayersRemaining =
                newState.players_remaining;
        }


        function renderState(
            newState
        ) {
            detectAnnouncements(
                newState
            );

            state = newState;

            localRemaining =
                Number(
                    state.remaining_seconds
                );

            lastTickAt =
                performance.now();

            if (
                state.status === "COMPLETED"
            ) {
                timerElement.textContent =
                    "GG";
            } else {
                timerElement.textContent =
                    formatTime(
                        localRemaining
                    );
            }

            levelElement.textContent =
                state.current_level.position;

            smallElement.textContent =
                state.current_level.small_blind;

            bigElement.textContent =
                state.current_level.big_blind;

            remainingElement.textContent =
                state.players_remaining;

            statusElement.textContent =
                state.status;

            statusElement.dataset.status =
                state.status;


            if (state.next_level) {
                nextElement.textContent =
                    (
                        state.next_level.small_blind
                        +
                        " / "
                        +
                        state.next_level.big_blind
                    );
            } else {
                nextElement.textContent =
                    "FINAL LEVEL";
            }


            renderPayouts();
            updateProgress();

            errorElement.hidden =
                true;
        }


        async function syncState() {
            try {
                const response =
                    await fetch(
                        (
                            `/api/tournaments/`
                            +
                            `${tournamentId}`
                            +
                            `/state`
                        ),
                        {
                            headers: {
                                "Accept":
                                    "application/json",
                            },
                        }
                    );

                const payload =
                    await response.json();

                if (!response.ok) {
                    throw new Error(
                        payload.error
                        ||
                        "State request failed."
                    );
                }

                renderState(
                    payload
                );
            } catch (error) {
                errorElement.hidden =
                    false;

                console.error(
                    error
                );
            }
        }


        function visualTick() {
            if (
                state
                &&
                state.status === "RUNNING"
            ) {
                const now =
                    performance.now();

                const elapsed =
                    (
                        now
                        - lastTickAt
                    )
                    / 1000;

                if (elapsed >= 1) {
                    const wholeSeconds =
                        Math.floor(
                            elapsed
                        );

                    localRemaining =
                        Math.max(
                            0,
                            localRemaining
                            - wholeSeconds
                        );

                    lastTickAt +=
                        wholeSeconds
                        * 1000;

                    timerElement.textContent =
                        formatTime(
                            localRemaining
                        );
                }
            }

            requestAnimationFrame(
                visualTick
            );
        }


        fullscreenButton
            .addEventListener(
                "click",
                async () => {
                    try {
                        if (
                            !document.fullscreenElement
                        ) {
                            await document
                                .documentElement
                                .requestFullscreen();
                        } else {
                            await document
                                .exitFullscreen();
                        }
                    } catch (error) {
                        console.error(
                            error
                        );
                    }
                }
            );


        document.addEventListener(
            "fullscreenchange",
            () => {
                fullscreenButton.textContent =
                    document.fullscreenElement
                        ? "EXIT FULLSCREEN"
                        : "ENTER FULLSCREEN";
            }
        );


        soundButton
            .addEventListener(
                "click",
                () => {
                    soundEnabled =
                        !soundEnabled;

                    soundButton.textContent =
                        soundEnabled
                            ? "SOUND ON"
                            : "SOUND OFF";
                }
            );


        function showCursor() {
            document.body
                .classList
                .remove(
                    "cursor-hidden"
                );

            if (cursorTimeout) {
                clearTimeout(
                    cursorTimeout
                );
            }

            if (
                document.fullscreenElement
            ) {
                cursorTimeout =
                    setTimeout(
                        () => {
                            document.body
                                .classList
                                .add(
                                    "cursor-hidden"
                                );
                        },
                        2500
                    );
            }
        }


        document.addEventListener(
            "mousemove",
            showCursor
        );

        document.addEventListener(
            "keydown",
            showCursor
        );


        syncState();

        setInterval(
            syncState,
            2000
        );

        requestAnimationFrame(
            visualTick
        );
    }
);