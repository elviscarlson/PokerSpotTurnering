"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-leo-page]");
    if (!page) return;
    const button = page.querySelector("[data-leo-strike]");
    const response = page.querySelector("[data-leo-response]");
    const lines = [
        "Alla andra checkar respektfullt.",
        "Svärdet är vasst. Pokerfejset är vassare.",
        "Leo synar. Bordet svettas.",
        "Marker? Leo spelar med legendstatus.",
    ];
    let turn = 0;
    button.addEventListener("click", () => {
        button.disabled = true;
        response.textContent = lines[turn++ % lines.length];
        page.classList.add("leo-striking");
        setTimeout(() => {
            page.classList.remove("leo-striking");
            button.disabled = false;
        }, 750);
    });
});
