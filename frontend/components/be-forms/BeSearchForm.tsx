"use client"

import {useEffect, useRef} from "react";
import { usePathname } from 'next/navigation';
import './be-style.css';

interface BeSearchFormProps {
    formType?: string | null;
}

export function BeSearchForm({formType}: BeSearchFormProps) {
    const pathname = usePathname();
    const containerRef = useRef<HTMLDivElement>(null);
    const observerRef = useRef<MutationObserver>(null);

    const initSearchForm = () => {
        if (containerRef.current) {
            containerRef.current.innerHTML = '';
        }

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
        }(window, [
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

    useEffect(() => {
        initSearchForm();

        const targetNode = document.documentElement;
        const observer = new MutationObserver((mutations) => {
            mutations.forEach((mutation) => {
                if (mutation.attributeName === "lang") {
                    initSearchForm();
                }
            });
        });

        observer.observe(targetNode, { attributes: true, attributeFilter: ["lang"] });
        observerRef.current = observer;

        return () => {
            observer.disconnect();
            if (containerRef.current) containerRef.current.innerHTML = '';
        };
    }, [pathname]);

    return (
        <div className="block-search-wrapper">
            <div id="block-search" className={`notranslate block-search ${formType ? 'block-search--' + formType : ''}`}>
                <div ref={containerRef} id="be-search-form" className="be-container">
                    <a href="https://exely.com/" rel="nofollow" target="_blank">Hotel management software</a>
                </div>
            </div>
        </div>
    );
}
