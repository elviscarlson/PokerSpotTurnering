"use strict";

document.addEventListener("DOMContentLoaded", () => {
    const page = document.querySelector("[data-friend-page]");
    if (!page) return;
    const button = page.querySelector("[data-friend-action]");
    const response = page.querySelector("[data-friend-response]");
    const lines = JSON.parse(page.dataset.lines);
    const image = page.querySelector(".friend-image");
    const originalSource = image.src;
    const originalAlt = image.alt;
    let alternate = false;
    let turn = 0;
    button.addEventListener("click", () => {
        button.disabled = true;
        if (image.dataset.alternateSrc) {
            alternate = !alternate;
            image.src = alternate ? image.dataset.alternateSrc : originalSource;
            image.alt = alternate ? image.dataset.alternateAlt : originalAlt;
            page.classList.toggle("friend-alternate", alternate);
        }
        response.textContent = lines[turn++ % lines.length];
        page.classList.add("friend-acting");
        setTimeout(() => {
            page.classList.remove("friend-acting");
            button.disabled = false;
        }, 1500);
    });
});
