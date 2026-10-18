"use strict";

document.addEventListener("DOMContentLoaded", () => {
    document.querySelectorAll("[data-cash-champion]").forEach(card => {
        const button = card.querySelector("[data-celebrate-winner]");
        const response = card.querySelector("[data-champion-response]");
        button.addEventListener("click", () => {
            button.disabled = true;
            card.classList.add("cash-champion-celebrating");
            response.textContent = "Tack till kvällens sponsorer. Ni vet vilka ni är. ♠";
            setTimeout(() => {
                card.classList.remove("cash-champion-celebrating");
                button.disabled = false;
            }, 1600);
        });
    });
    const namespace = "http://www.w3.org/2000/svg";
    const money = value => `${value > 0 ? "+" : ""}${(value / 100).toLocaleString("sv-SE", {maximumFractionDigits: 2})} kr`;
    const element = (name, attributes = {}, content) => {
        const node = document.createElementNS(namespace, name);
        Object.entries(attributes).forEach(([key, value]) => node.setAttribute(key, value));
        if (content !== undefined) node.textContent = content;
        return node;
    };
    document.querySelectorAll("[data-cash-chart]").forEach(chart => {
        const values = JSON.parse(chart.querySelector("[data-chart-values]").textContent);
        const drawing = chart.querySelector("[data-chart-drawing]");
        const readout = chart.querySelector("[data-chart-readout]");
        if (!values.length) return;
        const draw = () => {
            const width = Math.max(260, drawing.clientWidth);
            const height = 245, left = 72, right = width - 16, top = 25, bottom = 205;
            const low = Math.min(0, ...values.map(point => point.value));
            const high = Math.max(0, ...values.map(point => point.value));
            const range = high - low || 100;
            const x = index => left + index / Math.max(1, values.length - 1) * (right - left);
            const y = value => bottom - (value - low) / range * (bottom - top);
            const svg = element("svg", {viewBox: `0 0 ${width} ${height}`, role: "img", "aria-label": "Samlat netto över tid i kronor"});
            svg.append(element("title", {}, "Samlat cashgame-resultat efter varje avslutad spelkväll"));
            svg.append(element("desc", {}, "Nollinjen är streckad. Alla belopp finns också i resultattabellen. Fokusera en punkt för datum och nettobelopp."));
            [low, high].filter((value, index, list) => list.indexOf(value) === index).forEach(value => {
                svg.append(element("line", {x1: left, x2: right, y1: y(value), y2: y(value), stroke: "#ffffff12"}));
                svg.append(element("text", {x: left - 8, y: y(value) + 4, "text-anchor": "end", fill: "#b4b4ba", "font-size": 10}, money(value)));
            });
            svg.append(element("line", {x1: left, x2: right, y1: y(0), y2: y(0), stroke: "#ffffff50", "stroke-dasharray": "4 5"}));
            svg.append(element("polyline", {points: values.map((point, index) => `${x(index)},${y(point.value)}`).join(" "), fill: "none", stroke: "#7edce7", "stroke-width": 2.5, "stroke-linejoin": "round"}));
            values.forEach((point, index) => {
                const label = `${point.label}: ${money(point.value)}`;
                const circle = element("circle", {cx: x(index), cy: y(point.value), r: 4, tabindex: 0, "aria-label": label});
                circle.append(element("title", {}, label));
                ["mouseenter", "focus", "click"].forEach(event => circle.addEventListener(event, () => { readout.textContent = label; }));
                svg.append(circle);
            });
            svg.append(element("text", {x: left, y: 235, fill: "#707076", "font-size": 11}, "Start"));
            svg.append(element("text", {x: right, y: 235, "text-anchor": "end", fill: "#707076", "font-size": 11}, `${values.length - 1} spelkvällar`));
            drawing.replaceChildren(svg);
        };
        draw();
        if (window.ResizeObserver) new ResizeObserver(draw).observe(drawing);
        else window.addEventListener("resize", draw);
    });
});
