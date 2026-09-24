"use strict";


document.addEventListener(
    "DOMContentLoaded",
    () => {
        const flashMessages =
            document.querySelectorAll(
                ".flash-message"
            );


        flashMessages.forEach(
            (
                flash,
                index
            ) => {
                setTimeout(
                    () => {
                        flash.style.transition =
                            (
                                "opacity 220ms ease, "
                                +
                                "transform 220ms ease"
                            );

                        flash.style.opacity =
                            "0";

                        flash.style.transform =
                            "translateY(-6px)";

                        setTimeout(
                            () => {
                                flash.remove();
                            },
                            240
                        );
                    },
                    4200
                    + (
                        index
                        * 300
                    )
                );
            }
        );
    }
);