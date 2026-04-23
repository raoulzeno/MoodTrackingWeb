 import { supabaseClient } from "/static/js/supabaseConfig.js"
 
 
 export function showToast(message, isError = false) {
            const toast = document.getElementById("toast");
            const toastMessage = document.getElementById("toast-message");
            const toastIcon = document.getElementById("toast-icon");

            toastMessage.innerText = message;

            if (isError) {
                toastIcon.className = "inline-flex items-center justify-center shrink-0 w-8 h-8 rounded-lg bg-red-500/20 text-red-400 text-xl";
                toastIcon.innerHTML = "❌";
            } else {
                toastIcon.className = "inline-flex items-center justify-center shrink-0 w-8 h-8 rounded-lg bg-green-500/20 text-green-400 text-xl";
                toastIcon.innerHTML = "✅"
            }

            toast.classList.remove("opacity-0", "translate-y-4", "pointer-events-none");
            toast.classList.add("opacity-100", "translate-y-0")

            setTimeout(() => {
                toast.classList.remove("opacity-100", "translate-y-0");
                toast.classList.add("opacity-0", "translate-y-4", "pointer-events-none")
            }, 3000);
        }

export function toggleMenu() {
                const menu = document.getElementById("mobile-menu");
                menu.classList.toggle("hidden");
            }

export async function handleLogout() {
                try {
                    const { error } = await supabaseClient.auth.signOut();

                    if (error) throw error;

                    window.location.href = "/login";
                } catch (error) {
                    console.error("Error logging out: ", error.message);
                    showToast("Failed to log out: " + error.message, true)
                }
            }

export  async function loadTrackingItems() {
                const { data: { session }} = await supabaseClient.auth.getSession();
                if (!session) return;

                fetch("/api/user-tracking-items", {
                    headers: { "Authorization": `Bearer ${session.access_token}`}
                })
                .then(response => response.json())
                .then(data => {
                    const actContainer = document.getElementById("activities-container")
                    const subContainer = document.getElementById("substances-container")

                    actContainer.innerHTML = "";
                    subContainer.innerHTML = "";

                    data.activities.forEach(act => {
                        const actName = act.name.charAt(0).toUpperCase() + act.name.slice(1);
                        actContainer.innerHTML += `
                            <div class="flex items-center gap-2">
                                <input type="checkbox" id="act-${act.id}" name="activities" data-id="${act.id}" class="hidden peer">
                                <label for="act-${act.id}" class="inline-block px-5 py-2 rounded-full border border-slate-700 bg-slate-800 text-slate-300 font-semibold cursor-pointer transition-all duration-200 select-none hover:bg-slate-700 peer-checked:bg-indigo-600 peer-checked:border-indigo-500 peer-checked:text-white peer-checked:shadow-[0_0_12px_rgba(99,102,241,0.4)]">${actName}</label>
                            </div>
                        `;
                    });
                    data.substances.forEach(sub => {
                        const subName = sub.name.charAt(0).toUpperCase() + sub.name.slice(1);
                        subContainer.innerHTML += `
                            <div class="p-4 bg-slate-900 rounded-xl shadow-sm border border-slate-700">
                                <div class="flex items-center gap-3">
                                    <input type="checkbox" id="substance-${sub.id}" name="substances" data-id="${sub.id}" value="slider-container-${sub.id}" class="w-5 h-5 accent-blue-500 cursor-pointer" onclick="displaySlider('slider-container-${sub.id}', 'value-${sub.id}', this)">
                                    <label for="substance-${sub.id}" class="text-lg font-semibold text-slate-200 cursor-pointer">${subName}</label>
                                </div>
                                <div id="slider-container-${sub.id}" style="display: none;" class="mt-4 pl-8">
                                    <input type="range" id="slider-${sub.id}" min="1" max="10" value="1" class="w-full h-2 bg-slate-700 rounded-lg appearance-none cursor-pointer focus:outline-none [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-6 [&::-webkit-slider-thumb]:h-6 [&::-webkit-slider-thumb]:bg-blue-500 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:transition-all [&::-webkit-slider-thumb]:hover:bg-blue-400 [&::-webkit-slider-thumb]:hover:scale-110" oninput="document.getElementById('value-${sub.id}').innerText = this.value + ' unit(s)'">
                                    <div class="mt-2 text-slate-400 font-medium">
                                        <span id="value-${sub.id}">1 unit(s)</span>
                                    </div>
                                </div>
                            </div>
                        `;
                    });
                })
                .catch(error => console.error("Error loading itmes:", error))
            }

export  async function getWeather() {
                const { data : { session }} = await supabaseClient.auth.getSession();

                if (!session) {
                    window.location.href = "/login";
                    return;
                }

                try {
                    const response = await fetch("/get-weather", {
                        method: "GET",
                        headers: {
                            "Authorization": `Bearer ${session.access_token}`
                        }
                    });
                    const data = await response.json()
                    if (!response.ok) throw new Error(data.message)
                    
                    document.getElementById("weather-display").innerText = data["weather"];
                } catch (error) {
                    showToast("Error" + error.message, true)
                }  
            }

export  function showError(message) {
                const errorDiv = document.getElementById("auth-error");
                errorDiv.innerText = message;
                errorDiv.classList.remove("hidden");
            }

export  async function updateBanner() {
                const { data: { user }} = await supabaseClient.auth.getUser();
                if (user && user.user_metadata) {
                    const name = user.user_metadata.display_name;
                    document.getElementById("tracker-title").innerText = `${name}'s Tracker`
                }
            }
