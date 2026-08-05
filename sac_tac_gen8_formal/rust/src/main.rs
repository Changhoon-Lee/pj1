use std::env;

fn parse_csv(s: &str) -> Result<Vec<i128>, String> {
    if s.is_empty() {
        return Ok(vec![]);
    }
    s.split(',')
        .map(|x| x.parse::<i128>().map_err(|e| e.to_string()))
        .collect()
}

fn q_exact(mut v: Vec<i128>, margin: i128) -> Result<usize, String> {
    if v.iter().any(|x| *x < 0) {
        return Err("negative capacity".into());
    }
    if margin <= 0 {
        return Ok(0);
    }
    v.sort_by(|a, b| b.cmp(a));
    let mut total: i128 = 0;
    for (i, x) in v.iter().enumerate() {
        total = total.checked_add(*x).ok_or("overflow")?;
        if total >= margin {
            return Ok(i + 1);
        }
    }
    Ok(v.len() + 1)
}

fn q_hist(upper: Vec<i128>, count: Vec<i128>, margin: i128, n: i128) -> Result<i128, String> {
    if upper.len() != count.len() || upper.is_empty() {
        return Err("size".into());
    }
    if upper.iter().any(|x| *x < 0) || count.iter().any(|x| *x < 0) {
        return Err("negative".into());
    }
    if upper.windows(2).any(|w| w[0] >= w[1]) {
        return Err("unordered".into());
    }
    let total_count = count
        .iter()
        .try_fold(0_i128, |a, x| a.checked_add(*x).ok_or("overflow"))?;
    if total_count != n {
        return Err("count".into());
    }
    if margin <= 0 {
        return Ok(0);
    }
    let mut remaining = margin;
    let mut used = 0_i128;
    for (u, c) in upper.into_iter().zip(count).rev() {
        if u == 0 || c == 0 {
            continue;
        }
        let block = u.checked_mul(c).ok_or("overflow")?;
        if block >= remaining {
            let rounded = remaining.checked_add(u - 1).ok_or("overflow")? / u;
            return used.checked_add(rounded).ok_or("overflow".into());
        }
        remaining -= block;
        used = used.checked_add(c).ok_or("overflow")?;
    }
    n.checked_add(1).ok_or("overflow".into())
}

fn main() -> Result<(), String> {
    let a: Vec<String> = env::args().collect();
    match a.get(1).map(String::as_str) {
        Some("q") if a.len() == 4 => println!(
            "{}",
            q_exact(
                parse_csv(&a[2])?,
                a[3].parse::<i128>().map_err(|e| e.to_string())?
            )?
        ),
        Some("hist") if a.len() == 6 => println!(
            "{}",
            q_hist(
                parse_csv(&a[2])?,
                parse_csv(&a[3])?,
                a[4].parse::<i128>().map_err(|e| e.to_string())?,
                a[5].parse::<i128>().map_err(|e| e.to_string())?
            )?
        ),
        _ => return Err("usage: q CSV MARGIN | hist UPPERS COUNTS MARGIN N".into()),
    }
    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn support_exact() {
        assert_eq!(q_exact(vec![1, 4, 3], 7).unwrap(), 2);
        assert_eq!(q_exact(vec![1, 1], 3).unwrap(), 3);
    }

    #[test]
    fn histogram_lower() {
        assert_eq!(q_hist(vec![2, 4], vec![1, 3], 7, 4).unwrap(), 2);
    }

    #[test]
    fn rejects_unordered() {
        assert!(q_hist(vec![4, 2], vec![1, 3], 7, 4).is_err());
    }

    #[test]
    fn sentinel() {
        assert_eq!(q_hist(vec![1], vec![2], 3, 2).unwrap(), 3);
    }
}
