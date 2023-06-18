


const func= ()=>{

const price_element = document.querySelector('.items_price')
const shipping_element = document.querySelector('.shipping')
const total_element = document.querySelector('.total')
var price = price_element.innerHTML
var shipping = shipping_element.value

var price = parseInt(price.replace(/^\D+/g, ''))
var shipping = parseInt(shipping.replace(/^\D+/g, ''))
var total = price+shipping

if (price>0){

total_element.innerHTML= "₪ "+total.toString()
}
else{
total_element.innerHTML= "₪ 0"
}

}
func()
