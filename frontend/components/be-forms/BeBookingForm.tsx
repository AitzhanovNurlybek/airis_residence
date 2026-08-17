"use client"

import {useEffect} from "react";
import { usePathname } from 'next/navigation';
import './be-style.css';

export function BeBookingForm() {
    const pathname = usePathname();
    const loadBookingForm = (w: Window) => {
        /* eslint-disable */
        // @ts-ignore
        !function(e,n){
            // @ts-ignore
            var t="bookingengine",o="integration",i=e[t]=e[t]||{},a=i[o]=i[o]||{},r="__cq",c="__loader",d="getElementsByTagName";
            // @ts-ignore
            if(n=n||[],a[r]=a[r]?a[r].concat(n):n,!a[c]){a[c]=!0;var l=e.document,g=l[d]("head")[0]||l[d]("body")[0];
                // @ts-ignore
                !function n(i){if(0!==i.length){var a=l.createElement("script");a.type="text/javascript",a.async=!0,a.src="https://"+i[0]+"/integration/loader.js",
                    // @ts-ignore
                    a.onerror=a.onload=function(n,i){return function(){e[t]&&e[t][o]&&e[t][o].loaded||(g.removeChild(n),i())}}(a,(function(){n(i.slice(1,i.length))})),g.appendChild(a)}}(
                    ["kz-ibe.hopenapi.com", "ibe.hopenapi.com", "ibe.behopenapi.com"])}
        }(w, [
            ["setContext", "BE-INT-airisresidence_2026-08-13", "ru"],
            ["embed", "booking-form", {
                container: "be-booking-form"
            }],
            ["embed", "search-form", {
                container: "be-search-form"
            }]
        ]);
        /* eslint-enable */

        const container = document.documentElement;
        const mutationConfig = {attributes: true, attributeFilter: ["lang"]};
        const onMutate = function () {
            const beLang = document.documentElement.getAttribute("lang");

            /* eslint-disable */
            // @ts-ignore
            !function(e,n){
                // @ts-ignore
                var t="bookingengine",o="integration",i=e[t]=e[t]||{},a=i[o]=i[o]||{},r="__cq",c="__loader",d="getElementsByTagName";
                // @ts-ignore
                if(n=n||[],a[r]=a[r]?a[r].concat(n):n,!a[c]){a[c]=!0;var l=e.document,g=l[d]("head")[0]||l[d]("body")[0];
                    // @ts-ignore
                    !function n(i){if(0!==i.length){var a=l.createElement("script");a.type="text/javascript",a.async=!0,a.src="https://"+i[0]+"/integration/loader.js",
                        // @ts-ignore
                        a.onerror=a.onload=function(n,i){return function(){e[t]&&e[t][o]&&e[t][o].loaded||(g.removeChild(n),i())}}(a,(function(){n(i.slice(1,i.length))})),g.appendChild(a)}}(
                        ["kz-ibe.hopenapi.com", "ibe.hopenapi.com", "ibe.behopenapi.com"])}
            }(w, [
                ["setContext", "BE-INT-airisresidence_2026-08-13", beLang],
                ["embed", "booking-form", {
                    container: "be-booking-form"
                }],
                ["embed", "search-form", {
                    container: "be-search-form"
                }]
            ]);
            /* eslint-enable */
        };

        const observer = new MutationObserver(onMutate);
        observer.observe(container, mutationConfig);
    }

    useEffect(() => {
        loadBookingForm(window);
    }, [pathname]);

    return (
        <div id="be-booking-form" />
    );
}