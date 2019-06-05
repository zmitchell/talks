use std::time::Instant;

const SIZE: usize = 10_000;

#[inline(never)]
pub fn in_place() {
    let mut arr: [u32; SIZE] = [0; SIZE];
    for i in 0..SIZE {
        arr[i] += 1;
    }
}

#[inline(never)]
pub fn swapped() {
    let arr: [u32; SIZE] = [0; SIZE];
    let mut result: [u32; SIZE] = [0; SIZE];
    for i in 0..SIZE {
        result[i] = arr[i] + 1;
    }
    let _arr = result;
}


fn main() {
    in_place(); // warm up the cache
    let now = Instant::now();
    in_place();
    let elapsed = now.elapsed();
    println!("In Place: {:?}", elapsed);

    swapped(); // warm up the cache
    let now = Instant::now();
    swapped();
    let elapsed = now.elapsed();
    println!("Swapped:  {:?}", elapsed);
}
