// ======================================
// Dane
// ======================================

let tasks = [];

const topicsContainer = document.getElementById("topics");
const stagesContainer = document.getElementById("stages");
const editionsContainer = document.getElementById("editions");

const resultsContainer = document.getElementById("results");
const resultsCount = document.getElementById("resultsCount");

const topicMode = document.getElementById("topicMode");


// ======================================
// Start
// ======================================

document.addEventListener("DOMContentLoaded", init);

async function init() {

    try {

        const response = await fetch("data.json");

        if (!response.ok)
            throw new Error("Nie można wczytać data.json");

        tasks = await response.json();

        generateFilters();

        loadFiltersFromURL();

        applyFilters();

    }

    catch(err){

        console.error(err);

        resultsContainer.innerHTML = `
            <p>Nie udało się wczytać danych.</p>
        `;

    }

}


// ======================================
// Generowanie filtrów
// ======================================

function generateFilters(){

    generateTopics();

    generateStages();

    generateEditions();

}


// ======================================
// Tematy
// ======================================

function generateTopics(){

    const topics = new Set();

    tasks.forEach(task=>{

        task.tematy.forEach(topic=>{

            topics.add(topic);

        });

    });

    [...topics]
        .sort((a,b)=>a.localeCompare(b,"pl"))
        .forEach(topic=>{

            topicsContainer.appendChild(

                createCheckbox(
                    "topic",
                    topic,
                    topic
                )

            );

        });

}


// ======================================
// Etapy
// ======================================

function generateStages(){

    const stages = new Set();

    tasks.forEach(task=>{

        stages.add(task.etap);

    });

    const order = [
        "wst",
        "I",
        "II",
        "III",
        "F"
    ];

    [...stages]
        .sort((a,b)=>{

            return order.indexOf(a)-order.indexOf(b);

        })
        .forEach(stage=>{

            stagesContainer.appendChild(

                createCheckbox(
                    "stage",
                    stage,
                    stageLabel(stage)
                )

            );

        });

}


// ======================================
// Edycje
// ======================================

function generateEditions(){

    const editions = new Set();

    tasks.forEach(task=>{

        editions.add(Number(task.edycja));

    });

    [...editions]
        .sort((a,b)=>b-a)
        .forEach(edition=>{

            editionsContainer.appendChild(

                createCheckbox(
                    "edition",
                    edition,
                    edition
                )

            );

        });

}


// ======================================
// Tworzenie checkboxa
// ======================================

function createCheckbox(type,value,label){

    const wrapper = document.createElement("label");

    wrapper.className="checkbox";

    wrapper.innerHTML=`

        <input
            type="checkbox"
            class="${type}"
            value="${value}"
        >

        <span>${label}</span>

    `;

    return wrapper;

}


// ======================================
// Opisy etapów
// ======================================

function stageLabel(stage){

    switch(stage){

        case "wst":
            return "Wstępne";

        case "I":
            return "I etap";

        case "II":
            return "II etap";

        case "III":
            return "III etap";

        case "F":
            return "Finał";

        default:
            return stage;

    }

}
// ======================================
// Nasłuchiwanie zmian
// ======================================

document.addEventListener("change", e => {

    if (
        e.target.matches(".topic") ||
        e.target.matches(".stage") ||
        e.target.matches(".edition") ||
        e.target.id === "topicMode"
    ) {

        updateURL();
        applyFilters();

    }

});


// ======================================
// Pobieranie zaznaczonych checkboxów
// ======================================

function getChecked(className){

    return [...document.querySelectorAll(`.${className}:checked`)]
        .map(el => el.value);

}


// ======================================
// Filtrowanie
// ======================================

function applyFilters(){

    const selectedTopics = getChecked("topic");
    const selectedStages = getChecked("stage");
    const selectedEditions = getChecked("edition");

    const andMode = topicMode.checked;

    const filtered = tasks.filter(task=>{

        //---------------------------------------------------
        // Tematy
        //---------------------------------------------------

        let topicMatch = true;

        if(selectedTopics.length){

            if(andMode){

                topicMatch = selectedTopics.every(topic =>
                    task.tematy.includes(topic)
                );

            }else{

                topicMatch = selectedTopics.some(topic =>
                    task.tematy.includes(topic)
                );

            }

        }

        //---------------------------------------------------
        // Etapy
        //---------------------------------------------------

        let stageMatch = true;

        if(selectedStages.length){

            stageMatch = selectedStages.includes(task.etap);

        }

        //---------------------------------------------------
        // Edycje
        //---------------------------------------------------

        let editionMatch = true;

        if(selectedEditions.length){

            editionMatch =
                selectedEditions.includes(String(task.edycja));

        }

        return topicMatch
            && stageMatch
            && editionMatch;

    });

    renderTasks(filtered);

}


// ======================================
// URL
// ======================================

function updateURL(){

    const params = new URLSearchParams();

    const topics = getChecked("topic");
    const stages = getChecked("stage");
    const editions = getChecked("edition");

    if(topics.length){

        params.set(
            "tematy",
            topics.join(",")
        );

    }

    if(stages.length){

        params.set(
            "etapy",
            stages.join(",")
        );

    }

    if(editions.length){

        params.set(
            "edycje",
            editions.join(",")
        );

    }

    if(topicMode.checked){

        params.set(
            "mode",
            "and"
        );

    }

    const query = params.toString();

    history.replaceState(
        {},
        "",
        query ? `?${query}` : location.pathname
    );

}


// ======================================
// Odczyt filtrów z URL
// ======================================

function loadFiltersFromURL(){

    const params = new URLSearchParams(location.search);

    const topics =
        (params.get("tematy") || "")
        .split(",")
        .filter(Boolean);

    const stages =
        (params.get("etapy") || "")
        .split(",")
        .filter(Boolean);

    const editions =
        (params.get("edycje") || "")
        .split(",")
        .filter(Boolean);

    if(params.get("mode")==="and"){

        topicMode.checked=true;

    }

    document.querySelectorAll(".topic").forEach(cb=>{

        cb.checked =
            topics.includes(cb.value);

    });

    document.querySelectorAll(".stage").forEach(cb=>{

        cb.checked =
            stages.includes(cb.value);

    });

    document.querySelectorAll(".edition").forEach(cb=>{

        cb.checked =
            editions.includes(cb.value);

    });

}
// ======================================
// Wyświetlana nazwa etapu
// ======================================

function displayStage(task){

    const stage = String(task.etap).trim().toLowerCase();
    const nr = String(task.nr).toUpperCase();

    if(stage === "wst"){

        if(nr.startsWith("A"))
            return "Wstępne A";

        if(nr.startsWith("B"))
            return "Wstępne B";

        return "Wstępne";

    }

    switch(stage){

        case "i":
            return "I etap";

        case "ii":
            return "II etap";

        case "iii":
            return "III etap";

        case "f":
            return "Finał";

        default:
            return task.etap;

    }

}


// ======================================
// Renderowanie wyników
// ======================================

function renderTasks(list){

    resultsContainer.innerHTML = "";

    resultsCount.textContent = list.length;


    if(list.length === 0){

        resultsContainer.innerHTML = `
            <div class="no-results">
                Nie znaleziono żadnych zadań.
            </div>
        `;

        return;

    }


    // Najnowsze edycje jako pierwsze

    list.sort((a,b)=>{

        if(Number(a.edycja)!==Number(b.edycja)){

            return Number(b.edycja)-Number(a.edycja);

        }


        return a.nr.localeCompare(
            b.nr,
            "pl",
            {
                numeric:true
            }
        );

    });




    list.forEach(task=>{


        const card = document.createElement("article");

        card.className = "task-card";




        const tags = task.tematy
            .map(topic => {

                return `
                    <span class="tag">
                        ${topic}
                    </span>
                `;

            })
            .join("");





        card.innerHTML = `


            <div class="task-header">


                <div class="task-number">

                    Zadanie ${task.nr}

                </div>



                <div class="task-meta">

                    ${task.edycja} OCh

                    <span class="separator">•</span>

                    ${displayStage(task)}

                </div>


            </div>





            <a 
                href="${task.link}" 
                target="_blank"
                class="task-link"
            >

                ${task.tytul}

            </a>





            <div class="task-topics">


            


                <div class="tags">

                    ${tags}

                </div>


            </div>





            ${
                task.komentarz

                ?

                `
                <div class="task-comment">

                    <strong>Uwagi:</strong>

                    ${task.komentarz}

                </div>
                `

                :

                ""

            }





        `;


        resultsContainer.appendChild(card);


    });


}