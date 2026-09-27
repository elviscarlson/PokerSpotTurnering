"use strict";


document.addEventListener(
    "DOMContentLoaded",
    () => {
        const app =
            document.querySelector(
                "[data-clock-app]"
            );

        if (!app) {
            return;
        }


        const tournamentId =
            app.dataset.tournamentId;

        const timerElement =
            app.querySelector(
                "[data-clock-timer]"
            );

        const levelElement =
            app.querySelector(
                "[data-level-number]"
            );

        const smallBlindElement =
            app.querySelector(
                "[data-small-blind]"
            );

        const bigBlindElement =
            app.querySelector(
                "[data-big-blind]"
            );

        const nextBlindsElement =
            app.querySelector(
                "[data-next-blinds]"
            );

        const statusElement =
            app.querySelector(
                "[data-clock-status]"
            );

        const errorElement =
            app.querySelector(
                "[data-clock-error]"
            );

        const playerList =
            app.querySelector(
                "[data-player-list]"
            );

        const playersRemaining =
            app.querySelector(
                "[data-players-remaining]"
            );

        const prizePoolElement =
            app.querySelector(
                "[data-prize-pool]"
            );

        const bountyPoolElement =
            app.querySelector(
                "[data-bounty-pool]"
            );

        const totalBuyinsElement =
            app.querySelector(
                "[data-total-buyins]"
            );

        const totalEntriesElement =
            app.querySelector(
                "[data-total-entries]"
            );

        const playersRemainingSmall =
            app.querySelector(
                "[data-players-remaining-small]"
            );

        const upcomingLevels =
            app.querySelector(
                "[data-upcoming-levels]"
            );

        const payoutList =
            app.querySelector(
                "[data-payout-list]"
            );

        const eventList =
            app.querySelector(
                "[data-event-list]"
            );

        const dialog =
            app.querySelector(
                "[data-elimination-dialog]"
            );

        const dialogName =
            app.querySelector(
                "[data-elimination-name]"
            );

        const eliminatorField =
            app.querySelector(
                "[data-eliminator-field]"
            );

        const eliminatorSelect =
            app.querySelector(
                "[data-eliminator-select]"
            );

        const confirmElimination =
            app.querySelector(
                "[data-confirm-elimination]"
            );

        const cancelElimination =
            app.querySelector(
                "[data-cancel-elimination]"
            );


        let state = null;

        let localRemaining = 0;

        let lastTickAt =
            performance.now();

        let eliminationTarget =
            null;

        let completionRedirectStarted =
            false;

        let nextLevelArmed =
            false;

        let nextLevelTimeout =
            null;


        function formatTime(
            seconds
        ) {
            const value =
                Math.max(
                    0,
                    Math.floor(seconds)
                );

            const minutes =
                Math.floor(
                    value / 60
                );

            const remainder =
                value % 60;

            return (
                String(minutes)
                    .padStart(
                        2,
                        "0"
                    )
                +
                ":"
                +
                String(remainder)
                    .padStart(
                        2,
                        "0"
                    )
            );
        }


        function showError(
            message
        ) {
            if (!message) {
                errorElement.hidden =
                    true;

                errorElement.textContent =
                    "";

                return;
            }

            errorElement.textContent =
                message;

            errorElement.hidden =
                false;
        }


        function renderPlayers() {
            playerList.innerHTML =
                "";

            const active =
                state.players.filter(
                    player =>
                        player.status
                        === "ACTIVE"
                );

            const eliminated =
                state.players
                    .filter(
                        player =>
                            player.status
                            === "ELIMINATED"
                    )
                    .sort(
                        (
                            a,
                            b
                        ) =>
                            a.placement
                            - b.placement
                    );


            active.forEach(
                player => {
                    const row =
                        document.createElement(
                            "div"
                        );

                    row.className =
                        "live-player-row";

                    const isWinner =
                        (
                            state.status
                            === "COMPLETED"
                            &&
                            state.winner
                            &&
                            state.winner
                                .entry_id
                            === player.entry_id
                        );

                    row.innerHTML = `
                        <div class="live-player-identity">

                            <div class="player-avatar">
                                ${
                                    isWinner
                                        ? "W"
                                        : player.name
                                            .charAt(0)
                                            .toUpperCase()
                                }
                            </div>

                            <div>

                                <strong>
                                    ${player.name}
                                </strong>

                                <span>
                                    ${
                                        isWinner
                                            ? "WINNER"
                                            : (
                                                player.bounty_count
                                                +
                                                " bounties · "
                                                +
                                                player.bounty_winnings
                                                +
                                                " kr"
                                            )
                                    }
                                </span>

                            </div>

                        </div>

                        ${
                            (
                                isWinner
                                ||
                                state.status
                                === "COMPLETED"
                            )
                                ? ""
                                : `
                                    <button
                                        class="eliminate-button"
                                        type="button"
                                    >
                                        Eliminate
                                    </button>
                                `
                        }
                    `;


                    const button =
                        row.querySelector(
                            ".eliminate-button"
                        );

                    if (button) {
                        button.addEventListener(
                            "click",
                            () => {
                                openElimination(
                                    player
                                );
                            }
                        );
                    }


                    playerList.appendChild(
                        row
                    );
                }
            );


            if (
                eliminated.length
            ) {
                const divider =
                    document.createElement(
                        "div"
                    );

                divider.className =
                    "player-list-divider";

                divider.textContent =
                    "ELIMINATED";

                playerList.appendChild(
                    divider
                );
            }


            eliminated.forEach(
                player => {
                    const row =
                        document.createElement(
                            "div"
                        );

                    row.className =
                        (
                            "live-player-row "
                            +
                            "live-player-row-eliminated"
                        );

                    row.innerHTML = `
                        <div class="live-player-identity">

                            <div class="player-avatar">
                                ${player.placement}
                            </div>

                            <div>

                                <strong>
                                    ${player.name}
                                </strong>

                                <span>
                                    ${player.placement}:e plats
                                    ·
                                    ${player.prize_winnings} kr
                                </span>

                            </div>

                        </div>

                        <div class="player-row-actions">

                            ${
                                (
                                    state.status
                                    === "RUNNING"
                                    ||
                                    state.status
                                    === "PAUSED"
                                )
                                    ? `
                                        <button
                                            class="restore-button reentry-button"
                                            type="button"
                                        >
                                            Re-entry
                                        </button>
                                    `
                                    : ""
                            }

                            ${
                                state.status
                                === "COMPLETED"
                                    ? ""
                                    : `
                                        <button
                                            class="restore-button undo-elimination-button"
                                            type="button"
                                        >
                                            Undo
                                        </button>
                                    `
                            }

                        </div>
                    `;


                    const reentryButton =
                        row.querySelector(
                            ".reentry-button"
                        );

                    if (
                        reentryButton
                    ) {
                        reentryButton
                            .addEventListener(
                                "click",
                                async () => {
                                    const confirmed =
                                        window.confirm(
                                            (
                                                `Registrera ett nytt inköp för `
                                                +
                                                `${player.name}?`
                                            )
                                        );

                                    if (
                                        !confirmed
                                    ) {
                                        return;
                                    }

                                    await reenterPlayer(
                                        player,
                                        reentryButton
                                    );
                                }
                            );
                    }


                    const undoButton =
                        row.querySelector(
                            ".undo-elimination-button"
                        );

                    if (
                        undoButton
                    ) {
                        undoButton
                            .addEventListener(
                                "click",
                                () => {
                                    restorePlayer(
                                        player
                                    );
                                }
                            );
                    }


                    playerList.appendChild(
                        row
                    );
                }
            );
        }


        function renderUpcomingLevels() {
            upcomingLevels.innerHTML =
                state.upcoming_levels
                    .map(
                        level => `
                            <div class="live-level-row">

                                <span>
                                    L${level.position}
                                </span>

                                <strong>
                                    ${level.small_blind}
                                    /
                                    ${level.big_blind}
                                </strong>

                                <small>
                                    ${
                                        Math.floor(
                                            level
                                                .duration_seconds
                                            / 60
                                        )
                                    } min
                                </small>

                            </div>
                        `
                    )
                    .join("");
        }


        function renderPayouts() {
            payoutList.innerHTML =
                state.payouts
                    .map(
                        payout => `
                            <div class="live-payout-row">

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


        function renderEvents() {
            if (
                !state.events.length
            ) {
                eventList.innerHTML = `
                    <div class="live-empty">
                        Inga händelser ännu.
                    </div>
                `;

                return;
            }

            eventList.innerHTML =
                state.events
                    .map(
                        event => `
                            <div class="live-event-row">

                                <span>
                                    ${event.message}
                                </span>

                            </div>
                        `
                    )
                    .join("");
        }


        function resetNextLevelConfirmation() {
            nextLevelArmed =
                false;

            if (
                nextLevelTimeout
            ) {
                clearTimeout(
                    nextLevelTimeout
                );

                nextLevelTimeout =
                    null;
            }

            const button =
                document.querySelector(
                    '[data-clock-action="next-level"]'
                );

            if (button) {
                button.textContent =
                    "Next →";

                button.classList.remove(
                    "clock-control-confirm"
                );
            }
        }


        function armNextLevel(
            button
        ) {
            nextLevelArmed =
                true;

            button.textContent =
                "Confirm next →";

            button.classList.add(
                "clock-control-confirm"
            );

            nextLevelTimeout =
                setTimeout(
                    () => {
                        resetNextLevelConfirmation();
                    },
                    3000
                );
        }


        function handleCompletion() {
            if (
                state.status
                !== "COMPLETED"
                ||
                completionRedirectStarted
            ) {
                return;
            }

            completionRedirectStarted =
                true;

            timerElement.textContent =
                "GG";

            setTimeout(
                () => {
                    window.location.href =
                        (
                            `/tournaments/`
                            +
                            `${tournamentId}`
                            +
                            `/result`
                        );
                },
                1600
            );
        }


        function renderState(
            newState
        ) {
            state =
                newState;

            if (
                prizePoolElement
            ) {
                prizePoolElement.textContent =
                    `${state.prize_pool}`;
            }


            if (
                bountyPoolElement
            ) {
                bountyPoolElement.textContent =
                    `${state.bounty_pool}`;
            }


            if (
                totalBuyinsElement
            ) {
                totalBuyinsElement.textContent =
                    `${state.total_buyins} KR`;
            }


            if (
                totalEntriesElement
            ) {
                totalEntriesElement.textContent =
                    state.total_entries;
            }

            localRemaining =
                Number(
                    state.remaining_seconds
                );

            lastTickAt =
                performance.now();

            timerElement.textContent =
                formatTime(
                    localRemaining
                );

            levelElement.textContent =
                state.current_level.position;

            smallBlindElement.textContent =
                state.current_level.small_blind;

            bigBlindElement.textContent =
                state.current_level.big_blind;

            statusElement.textContent =
                state.status;

            statusElement.dataset.status =
                state.status;

            playersRemaining.textContent =
                (
                    `${state.players_remaining}`
                    +
                    "/"
                    +
                    `${state.players_total}`
                );

            if (
                playersRemainingSmall
            ) {
                playersRemainingSmall.textContent =
                    state.players_remaining;
            }


            if (
                state.next_level
            ) {
                nextBlindsElement.textContent =
                    (
                        state.next_level
                            .small_blind
                        +
                        " / "
                        +
                        state.next_level
                            .big_blind
                    );
            } else {
                nextBlindsElement.textContent =
                    "FINAL LEVEL";
            }


            renderPlayers();
            renderUpcomingLevels();
            renderPayouts();
            renderEvents();
            updateControls();
            handleCompletion();
        }


        function updateControls() {
            const status =
                state?.status;


            document
                .querySelectorAll(
                    "[data-clock-action]"
                )
                .forEach(
                    button => {
                        const action =
                            button
                                .dataset
                                .clockAction;

                        let enabled =
                            true;


                        if (
                            action
                            === "start"
                        ) {
                            enabled =
                                status
                                === "READY";
                        }


                        if (
                            action
                            === "pause"
                        ) {
                            enabled =
                                status
                                === "RUNNING";
                        }


                        if (
                            action
                            === "resume"
                        ) {
                            enabled =
                                status
                                === "PAUSED";
                        }


                        if (
                            action
                            === "next-level"
                            ||
                            action
                            === "previous-level"
                            ||
                            action
                            === "reset-level"
                        ) {
                            enabled =
                                (
                                    status
                                    === "RUNNING"
                                    ||
                                    status
                                    === "PAUSED"
                                );
                        }


                        button.disabled =
                            !enabled;
                    }
                );


            document
                .querySelectorAll(
                    "[data-adjust-seconds]"
                )
                .forEach(
                    button => {
                        button.disabled =
                            !(
                                status
                                === "RUNNING"
                                ||
                                status
                                === "PAUSED"
                            );
                    }
                );
        }


        async function apiRequest(
            path,
            options = {}
        ) {
            const response =
                await fetch(
                    path,
                    options
                );

            const payload =
                await response.json();


            if (
                !response.ok
            ) {
                throw new Error(
                    payload.error
                    ||
                    "Åtgärden misslyckades."
                );
            }


            renderState(
                payload
            );

            showError("");
        }


        async function requestState() {
            await apiRequest(
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
        }


        async function postAction(
            action,
            body = null
        ) {
            const options = {
                method: "POST",
                headers: {
                    "Accept":
                        "application/json",
                },
            };


            if (
                body !== null
            ) {
                options.headers[
                    "Content-Type"
                ] = "application/json";

                options.body =
                    JSON.stringify(
                        body
                    );
            }


            await apiRequest(
                (
                    `/api/tournaments/`
                    +
                    `${tournamentId}`
                    +
                    `/`
                    +
                    `${action}`
                ),
                options
            );
        }


        async function reenterPlayer(
            player,
            button
        ) {
            button.disabled =
                true;

            const oldText =
                button.textContent;

            button.textContent =
                "Adding...";

            try {
                await apiRequest(
                    (
                        `/api/tournaments/`
                        +
                        `${tournamentId}`
                        +
                        `/players/`
                        +
                        `${player.entry_id}`
                        +
                        `/reentry`
                    ),
                    {
                        method: "POST",

                        headers: {
                            "Accept":
                                "application/json",
                        },
                    }
                );
            } catch (error) {
                button.disabled =
                    false;

                button.textContent =
                    oldText;

                showError(
                    error.message
                );
            }
        }


        function openElimination(
            player
        ) {
            eliminationTarget =
                player;

            dialogName.textContent =
                player.name;

            eliminatorSelect.innerHTML =
                "";


            if (
                state.bounty_enabled
            ) {
                eliminatorField.hidden =
                    false;

                const candidates =
                    state.players.filter(
                        candidate =>
                            (
                                candidate.status
                                === "ACTIVE"
                            )
                            &&
                            (
                                candidate.entry_id
                                !== player.entry_id
                            )
                    );


                candidates.forEach(
                    candidate => {
                        const option =
                            document.createElement(
                                "option"
                            );

                        option.value =
                            candidate.entry_id;

                        option.textContent =
                            candidate.name;

                        eliminatorSelect.appendChild(
                            option
                        );
                    }
                );
            } else {
                eliminatorField.hidden =
                    true;
            }


            dialog.showModal();
        }


        async function eliminateTarget() {
            if (
                !eliminationTarget
            ) {
                return;
            }


            const body = {};


            if (
                state.bounty_enabled
            ) {
                body.eliminated_by_entry_id =
                    Number(
                        eliminatorSelect.value
                    );
            }


            try {
                await apiRequest(
                    (
                        `/api/tournaments/`
                        +
                        `${tournamentId}`
                        +
                        `/players/`
                        +
                        `${eliminationTarget.entry_id}`
                        +
                        `/eliminate`
                    ),
                    {
                        method: "POST",

                        headers: {
                            "Accept":
                                "application/json",

                            "Content-Type":
                                "application/json",
                        },

                        body:
                            JSON.stringify(
                                body
                            ),
                    }
                );


                dialog.close();

                eliminationTarget =
                    null;
            } catch (error) {
                showError(
                    error.message
                );
            }
        }


        async function restorePlayer(
            player
        ) {
            try {
                await apiRequest(
                    (
                        `/api/tournaments/`
                        +
                        `${tournamentId}`
                        +
                        `/players/`
                        +
                        `${player.entry_id}`
                        +
                        `/restore`
                    ),
                    {
                        method: "POST",

                        headers: {
                            "Accept":
                                "application/json",
                        },
                    }
                );
            } catch (error) {
                showError(
                    error.message
                );
            }
        }


        confirmElimination
            .addEventListener(
                "click",
                eliminateTarget
            );


        cancelElimination
            .addEventListener(
                "click",
                () => {
                    dialog.close();

                    eliminationTarget =
                        null;
                }
            );


        document
            .querySelectorAll(
                "[data-clock-action]"
            )
            .forEach(
                button => {
                    button.addEventListener(
                        "click",
                        async () => {
                            const action =
                                button
                                    .dataset
                                    .clockAction;


                            if (
                                action
                                === "next-level"
                            ) {
                                if (
                                    !nextLevelArmed
                                ) {
                                    armNextLevel(
                                        button
                                    );

                                    return;
                                }

                                resetNextLevelConfirmation();
                            }


                            try {
                                await postAction(
                                    action
                                );
                            } catch (error) {
                                showError(
                                    error.message
                                );
                            }
                        }
                    );
                }
            );


        document
            .querySelectorAll(
                "[data-adjust-seconds]"
            )
            .forEach(
                button => {
                    button.addEventListener(
                        "click",
                        async () => {
                            try {
                                await postAction(
                                    "adjust-time",
                                    {
                                        delta_seconds:
                                            Number(
                                                button
                                                    .dataset
                                                    .adjustSeconds
                                            ),
                                    }
                                );
                            } catch (error) {
                                showError(
                                    error.message
                                );
                            }
                        }
                    );
                }
            );


        document.addEventListener(
            "keydown",
            event => {
                if (
                    event.target.matches(
                        "input, select, textarea"
                    )
                ) {
                    return;
                }


                if (
                    event.code
                    === "Space"
                ) {
                    event.preventDefault();


                    if (
                        state?.status
                        === "RUNNING"
                    ) {
                        postAction(
                            "pause"
                        ).catch(
                            error => {
                                showError(
                                    error.message
                                );
                            }
                        );
                    } else if (
                        state?.status
                        === "PAUSED"
                    ) {
                        postAction(
                            "resume"
                        ).catch(
                            error => {
                                showError(
                                    error.message
                                );
                            }
                        );
                    }
                }
            }
        );


        function visualTick() {
            if (
                state
                &&
                state.status
                === "RUNNING"
            ) {
                const now =
                    performance.now();

                const elapsed =
                    (
                        now
                        - lastTickAt
                    )
                    / 1000;


                if (
                    elapsed >= 1
                ) {
                    const seconds =
                        Math.floor(
                            elapsed
                        );

                    localRemaining =
                        Math.max(
                            0,
                            localRemaining
                            - seconds
                        );

                    lastTickAt +=
                        seconds
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


        async function sync() {
            if (
                completionRedirectStarted
            ) {
                return;
            }


            try {
                await requestState();
            } catch (error) {
                showError(
                    error.message
                );
            }
        }


        sync();


        setInterval(
            sync,
            3000
        );


        requestAnimationFrame(
            visualTick
        );
    }
);