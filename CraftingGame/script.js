//Starting the game (since i hide it before this script to show nothing when no scripts are used)
document.getElementById("game").hidden = false

//Defining the displays (the places where you get to see how much of that thing you have).
const display = document.getElementById("display")
const milkDisplay = document.getElementById("milk")
const breadDisplay = document.getElementById("bread")
const plateDisplay = document.getElementById("plate")
const milkbreadDisplay = document.getElementById("milkbread")
const milksandwichDisplay = document.getElementById("milksandwich")
const milkmealDisplay = document.getElementById("milkmeal")
const cheeseDisplay = document.getElementById("cheese")
const cheesesandwichDisplay = document.getElementById("cheesesandwich")

//your starting money
var money = 10
display.innerHTML = '$'  + money

//Buyables
var milk = 0
var bread = 0
var plate = 0

//Craftables (Through Crafting)
var milkbread = 0
var milksandwich = 0
var milkmeal = 0
var cheesesandwich = 0

//Crafables (Through Aging)
var cheese = 0

//Defining the function 'buy' which, allows you to buy stuff, pretty self-explanetory.
function buy (price, item) {
    if (money >= price) {
        money -= price
        if (item == 'milk') {
            milk += 1
            milkDisplay.innerHTML = milk
        } else if (item == 'bread') {
            bread += 1
            breadDisplay.innerHTML = bread
        } else if (item == 'plate'){
            plate += 1
            plateDisplay.innerHTML = plate
        } else {
            money += price
            console.error('item not registered');
        }
    }
    display.innerHTML = ' $'  + money
}

//Defining the function 'craft' which, crafts items into another, also kinda self-explanetory... (is also responible for aging)
function craft(item) {
    if (item == 'milkbread') { //Milk-Bread
        if (milk > 0 && bread > 0) {
            bread -= 1
            milk -= 1
            milkbread += 1
            breadDisplay.innerHTML = bread
            milkDisplay.innerHTML = milk
            milkbreadDisplay.innerHTML = milkbread
        }
    } else if (item == 'milksandwich') { //Milk Sandwich
        if (milkbread > 1) {
            milkbread -= 2
            milksandwich += 1
            milkbreadDisplay.innerHTML = milkbread
            milksandwichDisplay.innerHTML = milksandwich
        }
    } else if (item == 'milkmeal') { //Milk Meal
        if (milksandwich > 0 && milk > 0 && plate > 0) {
            milksandwich -= 1
            milk -= 1
            plate -= 1
            milkmeal += 1
            milksandwichDisplay.innerHTML = milksandwich
            milkDisplay.innerHTML = milk
            plateDisplay.innerHTML = plate
            milkmealDisplay.innerHTML = milkmeal
        }
    } else if (item == 'cheese') {
        if (milk > 0) {
            milk -= 1
            cheese += 1
            milkDisplay.innerHTML = milk
            cheeseDisplay.innerHTML = cheese
        }
    } else if (item == 'cheesesandwich') {
        if (cheese > 0 && bread > 1) {
            cheese -= 1
            bread -= 2
            cheesesandwich += 1
            cheeseDisplay.innerHTML = cheese
            breadDisplay.innerHTML = bread
            cheesesandwichDisplay.innerHTML = cheesesandwich
        }
    }
}

//Defining the function 'sell' which, sells things in return for money... do i even need to say it anymore??
function sell(price, item) {
    if (item == 'milkbread') { //Milk-Bread
        if (milkbread > 0) {
            milkbread -= 1
            money += price
            milkbreadDisplay.innerHTML = milkbread
            display.innerHTML = '$' + money
        }
    } else if (item == 'milksandwich') { //Milk Sandwich
        if (milksandwich > 0) {
            milksandwich -= 1
            money += price
            milksandwichDisplay.innerHTML = milksandwich
            display.innerHTML = '$' + money
        }
    } else if (item == 'milkmeal') { //Milk Meal
        if (milkmeal > 0) {
            milkmeal -= 1
            money += price
            milkmealDisplay.innerHTML = milkmeal
            display.innerHTML = '$' + money
        }
    } else if (item == 'cheesesandwich') { //Cheese Sandwich
        cheesesandwich -= 1
        money += price
        cheesesandwichDisplay.innerHTML = cheesesandwich
        display.innerHTML = '$' + money
    }
}