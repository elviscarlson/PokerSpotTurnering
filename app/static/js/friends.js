"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-friend-page]");
    if (!page) return;
    const button = page.querySelector("[data-friend-action]");
    const response = page.querySelector("[data-friend-response]");
    const lines = JSON.parse(page.dataset.lines);
    let turn = 0;
    button.addEventListener("click", () => {
        button.disabled = true;
        response.textContent = lines[turn++ % lines.length];
        page.classList.add("friend-acting");
        setTimeout(() => {
            page.classList.remove("friend-acting");
            button.disabled = false;
        }, 1500);
    });
});
