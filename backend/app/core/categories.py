"""Canonical product-category identifiers and Vietnamese display names."""

from types import MappingProxyType


_CLASS_LABELS = {
    "00": "Đầm / Váy Nữ",
    "01": "Đầm Dáng Dài / Maxi",
    "02": "Áo Thun / Áo Phông",
    "03": "Áo Nỉ, Hoodie & Áo Len",
    "04": "Quần Jeans Nữ",
    "05": "Nhẫn & Trang Sức",
    "06": "Bông Tai / Khuyên Tai",
    "07": "Mũ & Nón Thời Trang",
    "08": "Ví & Bóp Tiền",
    "09": "Vali & Túi Du Lịch",
    "10": "Ốp Lưng & Phụ Kiện Điện Thoại",
    "11": "Điện Thoại & Máy Tính Bảng",
    "12": "Đồng Hồ Treo Tường & Để Bàn",
    "13": "Đồ Dùng Cho Bé Ăn Dặm",
    "14": "Nồi Cơm Điện & Bếp Điện",
    "15": "Cà Phê & Dụng Cụ Pha Chế",
    "16": "Giày Đế Bằng & Giày Búp Bê",
    "17": "Giày Cao Gót & Sandal Nữ",
    "18": "Tủ Lạnh & Máy Lạnh",
    "19": "Thẻ Nhớ & USB Lưu Trữ",
    "20": "Bàn Ghế & Nội Thất",
    "21": "Dụng Cụ Thể Thao Vợt",
    "22": "Mũ Bảo Hiểm & Đồ Bảo Hộ",
    "23": "Găng Tay Thời Trang & Bảo Hộ",
    "24": "Đồng Hồ Đeo Tay",
    "25": "Thắt Lưng / Dây Nịt",
    "26": "Tai Nghe & Thiết Bị Âm Thanh",
    "27": "Mô Hình Xe & Đồ Chơi Phương Tiện",
    "28": "Áo Khoác Nam Nữ",
    "29": "Quần Nam",
    "30": "Giày Thể Thao & Sneaker",
    "31": "Bánh Kẹo & Đồ Ăn Vặt",
    "32": "Khẩu Trang & Vật Tư Y Tế",
    "33": "Gel Sát Khuẩn & Nước Rửa Tay",
    "34": "Mỹ Phẩm & Trang Điểm",
    "35": "Nước Hoa & Xịt Thơm",
    "36": "Dụng Cụ Vệ Sinh & Sửa Chữa Nhà Cửa",
    "37": "Laptop & Phụ Kiện Máy Tính",
    "38": "Bát Đĩa & Bàn Ăn",
    "39": "Bình Hoa & Decor Trang Trí",
    "40": "Thiết Bị Phòng Tắm & Vòi Sen",
    "41": "Sofa & Ghế Phòng Khách",
}

CLASS_LABELS = MappingProxyType(_CLASS_LABELS)
CANONICAL_CATEGORY_IDS = tuple(CLASS_LABELS)

